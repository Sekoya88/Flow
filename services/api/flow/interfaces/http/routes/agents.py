from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from flow.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)

from flow.application.genome_service import snapshot_genome
from flow.config import Settings
from flow.domain.genome import VersionStatus, VersionTrigger
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo, get_settings_dep
from flow.interfaces.http.schemas import AgentCreateIn, AgentPatchIn, ExecuteIn, VibeIn

router = APIRouter(prefix="/api/v1", tags=["agents"])

_VIBE_SYSTEM = """\
You are an AI agent configuration generator for Flow, an AI platform.

Given a description of what an agent should do, output a JSON object (no markdown, no extra text).

Available templates:
- "linear-3": Good for document Q&A, knowledge search, summarization from workspace docs
- "tool-agent": Good for web search, fetching URLs, research papers, any live-web tasks

Available tools (boolean flags):
- retrieve: Semantic search over workspace knowledge base (PDFs, docs, URLs)
- sandbox: Execute Python code
- long_term_memory: Remember past conversations
- tavily_search: Search the web (requires Tavily API key)
- fetch_webpage: Fetch and read content from any URL
- arxiv_search: Search ArXiv academic papers
- hf_papers: Fetch HuggingFace Daily Papers (trending AI/ML)

Output exactly this JSON shape:
{
  "name": "short 1-3 word title (e.g. 'Code Assistant')",
  "template": "linear-3" or "tool-agent",
  "system_prompt": "2-4 sentence instructions for the agent",
  "tools": {
    "retrieve": true/false,
    "sandbox": true/false,
    "long_term_memory": true/false,
    "tavily_search": true/false,
    "fetch_webpage": true/false,
    "arxiv_search": true/false,
    "hf_papers": true/false
  }
}
"""


@router.post("/agents", status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: AgentCreateIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if body.workspace_id not in allowed:
        raise HTTPException(status_code=403, detail="workspace not allowed")
    aid = await repo.create_agent(body.workspace_id, body.name, body.template, body.config)
    return {"id": str(aid)}


@router.get("/workspaces/{workspace_id}/agents")
async def list_agents(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if workspace_id not in allowed:
        raise HTTPException(status_code=403, detail="workspace not allowed")
    rows = await repo.list_agents(workspace_id)

    def _display_name(name: object, template: object) -> str:
        n = (str(name).strip() if name is not None else "") or ""
        if n:
            return n
        t = (str(template).strip() if template is not None else "") or ""
        if t:
            return t.replace("_", " ")
        return "Agent"

    return {
        "agents": [
            {
                "id": str(r["id"]),
                "name": _display_name(r["name"], r["template"]),
                "template": r["template"],
                "config": r["config"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


@router.post("/agents/{agent_id}/execute")
async def execute_agent(
    agent_id: UUID,
    body: ExecuteIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed_ws = {r["id"] for r in ws_rows}
    agent = None
    for ws in allowed_ws:
        agent = await repo.get_agent(agent_id, ws)
        if agent:
            break
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    workspace_id = agent["workspace_id"]

    thread_id: UUID | None = None
    if body.parent_execution_id is not None:
        parent_row = await repo.get_execution_for_user(body.parent_execution_id, user_id)
        if not parent_row:
            raise HTTPException(status_code=404, detail="parent execution not found")
        thread_id = parent_row["thread_id"]

    eid, resolved_thread = await repo.create_execution(
        agent_id, workspace_id, body.message, thread_id=thread_id
    )
    raw_cfg = agent["config"]
    agent_config = dict(raw_cfg) if isinstance(raw_cfg, dict) else {}
    # SSE uses Redis pub/sub per execution id — no hub registration needed.
    from flow.infrastructure.queue.client import enqueue_execution

    await enqueue_execution(
        execution_id=eid,
        workspace_id=workspace_id,
        agent_id=agent_id,
        user_id=user_id,
        user_message=body.message,
        agent_config=agent_config,
    )
    return {"execution_id": str(eid), "thread_id": str(resolved_thread)}


@router.post("/workspaces/{workspace_id}/agents/vibe")
async def vibe_agent(
    workspace_id: UUID,
    body: VibeIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> dict:
    """Use an LLM to generate an agent config from a freeform description."""
    ws_rows = await repo.list_workspaces_for_user(user_id)
    if workspace_id not in {r["id"] for r in ws_rows}:
        raise HTTPException(status_code=403, detail="workspace not allowed")

    from langchain_core.messages import HumanMessage, SystemMessage

    from flow.infrastructure.llm.providers import get_chat_model

    llm = get_chat_model(
        {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.3},
        fallback_api_keys={"openai": settings.openai_api_key, "anthropic": settings.anthropic_api_key},
    )
    if llm is None:
        return {
            "name": "Custom Agent",
            "template": "tool-agent",
            "system_prompt": "You are a helpful assistant.",
            "tools": {"retrieve": False, "sandbox": False, "long_term_memory": False, "tavily_search": True, "fetch_webpage": True, "arxiv_search": False, "hf_papers": False},
        }

    response = await llm.ainvoke([
        SystemMessage(content=_VIBE_SYSTEM),
        HumanMessage(content=body.description),
    ])
    raw = str(response.content).strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError:
        cfg = {
            "name": "Custom Agent",
            "template": "tool-agent",
            "system_prompt": raw[:500],
            "tools": {"retrieve": False, "sandbox": False, "long_term_memory": False, "tavily_search": True, "fetch_webpage": True, "arxiv_search": False, "hf_papers": False},
        }
    return cfg


@router.patch("/agents/{agent_id}")
async def patch_agent(
    agent_id: UUID,
    body: AgentPatchIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed_ws = {r["id"] for r in ws_rows}
    agent = None
    workspace_id: UUID | None = None
    for ws in allowed_ws:
        agent = await repo.get_agent(agent_id, ws)
        if agent:
            workspace_id = ws
            break
    if not agent or workspace_id is None:
        raise HTTPException(status_code=404, detail="agent not found")
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="no fields to update")
    if data.get("name") is not None:
        okn = await repo.update_agent_name(agent_id, workspace_id, data["name"])
        if not okn:
            raise HTTPException(status_code=500, detail="name update failed")
    agent = await repo.get_agent(agent_id, workspace_id)
    assert agent is not None
    tool_keys = ("retrieve", "sandbox", "long_term_memory", "tavily_search", "fetch_webpage", "arxiv_search", "hf_papers")
    config_changed = any(k in data for k in tool_keys) or data.get("system_prompt") is not None
    if config_changed:
        raw_cfg = agent["config"]
        cfg = dict(raw_cfg) if isinstance(raw_cfg, dict) else {}
        if any(k in data for k in tool_keys):
            tools = {**(cfg.get("tools") if isinstance(cfg.get("tools"), dict) else {})}
            defaults = {"retrieve": True, "sandbox": True, "long_term_memory": True, "tavily_search": False, "fetch_webpage": False, "arxiv_search": False, "hf_papers": False}
            merged = {**defaults, **tools}
            for field in tool_keys:
                if field in data and data[field] is not None:
                    merged[field] = data[field]
            cfg["tools"] = merged
        if data.get("system_prompt") is not None:
            cfg["system_prompt"] = data["system_prompt"]
        ok = await repo.update_agent_config(agent_id, workspace_id, cfg)
        if not ok:
            raise HTTPException(status_code=500, detail="update failed")
        try:
            await snapshot_genome(
                pool=repo._pool,
                agent_id=agent_id,
                workspace_id=workspace_id,
                trigger=VersionTrigger.CONFIG_PATCH,
                created_by=user_id,
                status=VersionStatus.ACTIVE,
            )
        except Exception:
            logger.warning("genome.snapshot_failed", exc_info=True)
    fresh = await repo.get_agent(agent_id, workspace_id)
    assert fresh is not None
    raw_cfg = fresh["config"]
    cfg = dict(raw_cfg) if isinstance(raw_cfg, dict) else {}
    return {"id": str(agent_id), "name": fresh["name"], "config": cfg}


@router.get("/agents/{agent_id}/stats")
async def agent_stats(
    agent_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Return agent stats: total runs, avg confidence, grade distribution, confidence trend."""
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed_ws = {r["id"] for r in ws_rows}
    agent = None
    for ws in allowed_ws:
        agent = await repo.get_agent(agent_id, ws)
        if agent:
            break
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    workspace_id = agent["workspace_id"]

    # Total runs + avg confidence from execution_events final payloads
    total_runs = await repo._pool.fetchval(
        "SELECT COUNT(*) FROM executions WHERE agent_id = $1 AND workspace_id = $2",
        agent_id, workspace_id,
    )

    # Confidence from execution_events where kind='final' and payload->>'confidence' exists
    conf_rows = await repo._pool.fetch(
        """
        SELECT
            e.id AS execution_id,
            ee.payload->>'confidence' AS conf,
            e.created_at
        FROM execution_events ee
        JOIN executions e ON e.id = ee.execution_id
        WHERE e.agent_id = $1 AND e.workspace_id = $2
          AND ee.kind = 'final'
          AND ee.payload->>'confidence' IS NOT NULL
        ORDER BY e.created_at DESC
        LIMIT 50
        """,
        agent_id, workspace_id,
    )
    confidences = []
    for r in conf_rows:
        try:
            confidences.append(float(r["conf"]))
        except (ValueError, TypeError):
            pass

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    confidence_trend = [
        {"confidence": c, "created_at": r["created_at"].isoformat(), "execution_id": str(r["execution_id"])}
        for c, r in zip(confidences[:20], conf_rows[:20])
    ]

    # Grade distribution from metacog KG nodes
    grade_rows = await repo._pool.fetch(
        """
        SELECT (metadata->>'grade')::int AS grade, COUNT(*)::int AS cnt
        FROM kg_nodes
        WHERE workspace_id = $1 AND node_type = 'metacog'
          AND metadata->>'grade' IS NOT NULL
          AND id IN (
            SELECT kge.source_node_id FROM kg_edges kge
            JOIN kg_nodes kn2 ON kn2.id = kge.target_node_id
            JOIN executions ex ON ex.id::text = kn2.metadata->>'execution_id'
            WHERE ex.agent_id = $2
          )
        GROUP BY (metadata->>'grade')::int
        ORDER BY grade
        """,
        workspace_id, agent_id,
    )
    grade_dist = {r["grade"]: r["cnt"] for r in grade_rows} if grade_rows else {}

    # Last run time
    last_run = await repo._pool.fetchval(
        "SELECT MAX(created_at) FROM executions WHERE agent_id = $1 AND workspace_id = $2",
        agent_id, workspace_id,
    )

    return {
        "agent_id": str(agent_id),
        "total_runs": int(total_runs or 0),
        "avg_confidence": round(avg_confidence, 3),
        "grade_distribution": grade_dist,
        "confidence_trend": confidence_trend,
        "last_run_at": last_run.isoformat() if last_run else None,
    }
