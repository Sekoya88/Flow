"""Unauthenticated endpoints for the local desktop app (macOS menubar)."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/local", tags=["local"])


@router.get("/agents")
async def list_agents(request: Request) -> dict:
    """All agents for the agent picker. No auth — local desktop only."""
    pool = request.app.state.pool
    rows = await pool.fetch("SELECT id, name FROM agents ORDER BY name")
    return {"agents": [{"id": str(r["id"]), "name": r["name"]} for r in rows]}


@router.get("/active-agents")
async def active_agents(request: Request) -> dict:
    """Return active agents (Redis), falling back to most-recent-execution agent from DB."""
    stream_hub = request.app.state.stream_hub
    ids = await stream_hub.get_active_agent_ids()
    if ids:
        return {"agents": [{"id": aid, "name": None} for aid in ids]}
    pool = request.app.state.pool
    row = await pool.fetchrow("SELECT a.id, a.name FROM executions e JOIN agents a ON a.id = e.agent_id ORDER BY e.created_at DESC LIMIT 1")
    if row:
        return {"agents": [{"id": str(row["id"]), "name": row["name"]}]}
    return {"agents": []}


@router.get("/agent-executions/{agent_id}")
async def agent_executions(agent_id: UUID, request: Request) -> dict:
    """Last 10 executions for an agent. No auth — local desktop only."""
    pool = request.app.state.pool
    rows = await pool.fetch(
        """
        SELECT id, status, user_message, created_at, completed_at
        FROM executions
        WHERE agent_id = $1
        ORDER BY created_at DESC
        LIMIT 10
        """,
        agent_id,
    )
    return {
        "executions": [
            {
                "id": str(r["id"]),
                "status": r["status"],
                "message": (r["user_message"] or "")[:120],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
            }
            for r in rows
        ]
    }


@router.get("/agent-memory/{agent_id}")
async def agent_memory(agent_id: UUID, request: Request) -> dict:
    """Last 20 memory entries for an agent. No auth — local desktop only."""
    pool = request.app.state.pool
    rows = await pool.fetch(
        """
        SELECT id, content, created_at
        FROM agent_memories
        WHERE agent_id = $1
        ORDER BY created_at DESC
        LIMIT 20
        """,
        agent_id,
    )
    return {
        "memories": [
            {
                "id": str(r["id"]),
                "content": r["content"][:240],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    }


@router.get("/agent-graph/{agent_id}")
async def agent_graph(agent_id: UUID, request: Request) -> dict:
    """Full graph payload for one agent: skills + tools + system_prompt flag + memory count."""
    pool = request.app.state.pool
    agent_row = await pool.fetchrow("SELECT id, name, template, config FROM agents WHERE id = $1", agent_id)
    if not agent_row:
        return {"agent": None, "skills": [], "tools": [], "has_system_prompt": False, "memory_count": 0}

    raw_config = agent_row["config"]
    config: dict = json.loads(raw_config) if isinstance(raw_config, str) else (raw_config or {})
    tools_enabled = [k for k, v in (config.get("tools") or {}).items() if v]
    has_system_prompt = bool((config.get("system_prompt") or "").strip())

    skills = await pool.fetch(
        """
        SELECT s.id, s.name, s.use_count, s.category,
               COALESCE(
                   CASE WHEN b.total_pulls > 0 THEN b.total_reward / b.total_pulls END,
                   s.score
               ) AS score
        FROM agent_skills s
        LEFT JOIN skill_bandit_arms b ON b.skill_id = s.id AND b.agent_id = $1
        WHERE s.agent_id = $1 AND s.active = true
        ORDER BY score DESC NULLS LAST
        LIMIT 12
        """,
        agent_id,
    )

    mem_count = await pool.fetchval("SELECT COUNT(*) FROM agent_memories WHERE agent_id = $1", agent_id)

    return {
        "agent": {
            "id": str(agent_row["id"]),
            "name": agent_row["name"],
            "template": agent_row["template"],
        },
        "skills": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "score": round(float(r["score"]), 3) if r["score"] is not None else 0.5,
                "use_count": r["use_count"],
                "category": r["category"] or "General",
            }
            for r in skills
        ],
        "tools": tools_enabled,
        "has_system_prompt": has_system_prompt,
        "memory_count": int(mem_count or 0),
    }


@router.post("/agent-skills")
async def create_agent_skill(request: Request) -> dict:
    """Create or upsert a skill for an agent. No auth — local desktop only."""
    body = await request.json()
    try:
        agent_id = UUID(body["agent_id"])
    except (KeyError, ValueError):
        return {"error": "agent_id required"}
    name = str(body.get("name", "")).strip()[:200]
    content_md = str(body.get("content_md", "")).strip()[:10000]
    if not name or not content_md:
        return {"error": "name and content_md required"}

    pool = request.app.state.pool
    row = await pool.fetchrow("SELECT workspace_id FROM agents WHERE id = $1", agent_id)
    if not row:
        return {"error": "agent not found"}

    sid = await pool.fetchval(
        """
        INSERT INTO agent_skills (agent_id, workspace_id, name, content_md, active)
        VALUES ($1, $2, $3, $4, true)
        ON CONFLICT (agent_id, name)
        DO UPDATE SET content_md = EXCLUDED.content_md, active = true
        RETURNING id
        """,
        agent_id,
        row["workspace_id"],
        name,
        content_md,
    )
    return {"id": str(sid)}


@router.post("/agent-knowledge")
async def ingest_agent_knowledge(request: Request) -> dict:
    """Ingest plain-text knowledge as an agent memory entry. No auth — local desktop only."""
    body = await request.json()
    try:
        agent_id = UUID(body["agent_id"])
    except (KeyError, ValueError):
        return {"error": "agent_id required"}
    title = str(body.get("title", "Knowledge")).strip()[:200]
    content = str(body.get("content", "")).strip()[:8000]
    if not content:
        return {"error": "content required"}

    pool = request.app.state.pool
    row = await pool.fetchrow("SELECT workspace_id FROM agents WHERE id = $1", agent_id)
    if not row:
        return {"error": "agent not found"}

    mid = await pool.fetchval(
        "INSERT INTO agent_memories (agent_id, workspace_id, content) VALUES ($1, $2, $3) RETURNING id",
        agent_id,
        row["workspace_id"],
        f"[Knowledge: {title}]\n{content}",
    )
    return {"id": str(mid)}


@router.post("/agent-memory")
async def add_agent_memory(request: Request) -> dict:
    """Add a rule or episodic memory entry for an agent. No auth — local desktop only."""
    body = await request.json()
    try:
        agent_id = UUID(body["agent_id"])
    except (KeyError, ValueError):
        return {"error": "agent_id required"}
    content = str(body.get("content", "")).strip()[:2000]
    if not content:
        return {"error": "content required"}

    pool = request.app.state.pool
    row = await pool.fetchrow("SELECT workspace_id FROM agents WHERE id = $1", agent_id)
    if not row:
        return {"error": "agent not found"}

    mid = await pool.fetchval(
        "INSERT INTO agent_memories (agent_id, workspace_id, content) VALUES ($1, $2, $3) RETURNING id",
        agent_id,
        row["workspace_id"],
        content,
    )
    return {"id": str(mid)}


@router.get("/agent-skills/{agent_id}")
async def agent_skills(agent_id: UUID, request: Request) -> dict:
    """Top skills with bandit scores for the skill graph. No auth — local desktop only."""
    pool = request.app.state.pool
    rows = await pool.fetch(
        """
        SELECT s.id, s.name, s.use_count, s.category,
               COALESCE(
                   CASE WHEN b.total_pulls > 0 THEN b.total_reward / b.total_pulls ELSE NULL END,
                   s.score
               ) AS bandit_score
        FROM agent_skills s
        LEFT JOIN skill_bandit_arms b ON b.skill_id = s.id AND b.agent_id = $1
        WHERE s.agent_id = $1 AND s.active = true
        ORDER BY bandit_score DESC
        LIMIT 12
        """,
        agent_id,
    )
    return {
        "skills": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "score": round(float(r["bandit_score"]), 3),
                "use_count": r["use_count"],
                "category": r["category"] or "General",
            }
            for r in rows
        ]
    }
