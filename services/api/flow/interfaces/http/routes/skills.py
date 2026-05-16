from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from flow.application.skill_parser import parse_skill_md
from flow.application.skill_playground import run_skill_test
from flow.config import Settings
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo, get_settings_dep

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


class SkillCreateIn(BaseModel):
    workspace_id: UUID
    agent_id: UUID
    name: str = Field(min_length=1, max_length=200)
    content_md: str = Field(min_length=1, max_length=10000)


class SkillOut(BaseModel):
    id: str
    name: str
    version: int
    content_md: str
    description: str = ""
    allowed_tools: list[str] = []
    triggers: list[str] = []
    metadata: dict = {}
    active: bool = True
    score: float = 1.0
    use_count: int = 0
    created_at: str = ""


@router.get("")
async def list_skills(
    workspace_id: UUID,
    agent_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    rows = await repo.list_active_skills(agent_id, workspace_id)
    skills = []
    for r in rows:
        parsed = parse_skill_md(r["content_md"])
        skills.append({
            "id": str(r["id"]),
            "name": parsed.name if parsed.name != "unnamed" else r["name"],
            "version": r["version"],
            "content_md": r["content_md"],
            "description": parsed.description,
            "allowed_tools": parsed.allowed_tools,
            "triggers": parsed.triggers,
            "metadata": parsed.metadata,
            "active": True,
            "score": r.get("score", 1.0) if hasattr(r, "get") else 1.0,
            "use_count": r.get("use_count", 0) if hasattr(r, "get") else 0,
            "created_at": r["created_at"].isoformat(),
        })
    return {"skills": skills}


@router.post("")
async def create_skill(
    body: SkillCreateIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    sid = await repo.upsert_agent_skill(
        agent_id=body.agent_id,
        workspace_id=body.workspace_id,
        name=body.name,
        content_md=body.content_md,
    )
    return {"id": str(sid)}


@router.get("/history")
async def skill_history(
    agent_id: UUID,
    name: str,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    rows = await repo.get_skill_history(agent_id, name)
    return {
        "versions": [
            {
                "id": str(r["id"]),
                "version": r["version"],
                "content_md": r["content_md"],
                "active": r["active"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


@router.delete("/{skill_id}")
async def deactivate_skill(
    skill_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await repo._pool.execute(
        "UPDATE agent_skills SET active = false WHERE id = $1", skill_id
    )
    return {"deactivated": True}


# ── Skills Hub ───────────────────────────────────────────────────────────────


class SkillTestIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


def _catalog_row_to_out(row) -> dict:
    parsed = parse_skill_md(row["content_md"])
    return {
        "id": str(row["id"]),
        "agent_id": str(row["agent_id"]),
        "agent_name": row["agent_name"],
        "name": parsed.name if parsed.name != "unnamed" else row["name"],
        "version": row["version"],
        "description": parsed.description or (row["description"] or ""),
        "triggers": parsed.triggers or list(row["triggers"] or []),
        "allowed_tools": parsed.allowed_tools or list(row["allowed_tools"] or []),
        "metadata": parsed.metadata or dict(row["metadata"] or {}),
        "score": float(row["score"] or 0.0),
        "use_count": int(row["use_count"] or 0),
        "created_at": row["created_at"].isoformat(),
    }


@router.get("/catalog")
async def list_skills_catalog(
    workspace_id: Annotated[UUID, Query()],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    agent_id: Annotated[UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> dict:
    """Cross-agent catalog of active skills for the Skills Hub."""
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if workspace_id not in allowed:
        raise HTTPException(status_code=403, detail="workspace access denied")
    rows = await repo.list_skills_catalog(workspace_id, agent_id, q)
    return {"skills": [_catalog_row_to_out(r) for r in rows]}


@router.post("/{skill_id}/activate")
async def activate_skill_version(
    skill_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Make this historical version the active one; deactivate siblings."""
    row = await repo.activate_skill_version(skill_id)
    if row is None:
        raise HTTPException(status_code=404, detail="skill not found")
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "version": row["version"],
        "active": row["active"],
    }


@router.post("/{skill_id}/test")
async def test_skill(
    skill_id: UUID,
    body: SkillTestIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> StreamingResponse:
    """Stream LLM tokens for a single-skill, single-prompt isolated run."""
    skill = await repo.get_skill_by_id(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")

    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if skill["workspace_id"] not in allowed:
        raise HTTPException(status_code=403, detail="workspace access denied")

    async def event_generator():
        async for token in run_skill_test(
            settings=settings,
            skill_content_md=skill["content_md"],
            prompt=body.prompt,
        ):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
