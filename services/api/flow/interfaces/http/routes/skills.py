from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo

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
    active: bool
    score: float
    use_count: int
    created_at: str


@router.get("")
async def list_skills(
    workspace_id: UUID,
    agent_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    rows = await repo.list_active_skills(agent_id, workspace_id)
    return {
        "skills": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "version": r["version"],
                "content_md": r["content_md"],
                "active": True,
                "score": r.get("score", 1.0) if hasattr(r, "get") else 1.0,
                "use_count": r.get("use_count", 0) if hasattr(r, "get") else 0,
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


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
