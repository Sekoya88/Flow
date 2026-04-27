from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from flow.config import Settings, get_settings
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo
from flow.interfaces.http.schemas import AgentCreateIn, AgentPatchIn, ExecuteIn

router = APIRouter(prefix="/api/v1", tags=["agents"])


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
    request: Request,
    agent_id: UUID,
    body: ExecuteIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings)],
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
    eid = await repo.create_execution(agent_id, workspace_id, body.message)
    raw_cfg = agent["config"]
    agent_config = dict(raw_cfg) if isinstance(raw_cfg, dict) else {}
    request.app.state.stream_hub.register(eid)
    from flow.infrastructure.queue.client import enqueue_execution

    await enqueue_execution(
        execution_id=eid,
        workspace_id=workspace_id,
        agent_id=agent_id,
        user_id=user_id,
        user_message=body.message,
        agent_config=agent_config,
    )
    return {"execution_id": str(eid)}


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
    tool_keys = ("retrieve", "sandbox", "long_term_memory")
    if any(k in data for k in tool_keys):
        raw_cfg = agent["config"]
        cfg = dict(raw_cfg) if isinstance(raw_cfg, dict) else {}
        tools = {**(cfg.get("tools") if isinstance(cfg.get("tools"), dict) else {})}
        defaults = {"retrieve": True, "sandbox": True, "long_term_memory": True}
        merged = {**defaults, **tools}
        for field in tool_keys:
            if field in data and data[field] is not None:
                merged[field] = data[field]
        cfg["tools"] = merged
        ok = await repo.update_agent_config(agent_id, workspace_id, cfg)
        if not ok:
            raise HTTPException(status_code=500, detail="update failed")
    fresh = await repo.get_agent(agent_id, workspace_id)
    assert fresh is not None
    raw_cfg = fresh["config"]
    cfg = dict(raw_cfg) if isinstance(raw_cfg, dict) else {}
    return {"id": str(agent_id), "name": fresh["name"], "config": cfg}
