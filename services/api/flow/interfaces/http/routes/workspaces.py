from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr

from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


class RenameWorkspaceIn(BaseModel):
    name: str


class AddMemberIn(BaseModel):
    email: EmailStr
    role: str = "editor"  # admin | editor | viewer


async def _assert_workspace(user_id: UUID, workspace_id: UUID, repo: FlowRepository) -> None:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if workspace_id not in allowed:
        raise HTTPException(status_code=403, detail="workspace not allowed")


async def _assert_admin(user_id: UUID, workspace_id: UUID, repo: FlowRepository) -> None:
    await _assert_workspace(user_id, workspace_id, repo)
    if not await repo.is_workspace_admin(workspace_id, user_id):
        raise HTTPException(status_code=403, detail="admin role required")


@router.patch("/{workspace_id}")
async def rename_workspace(
    workspace_id: UUID,
    body: RenameWorkspaceIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await _assert_admin(user_id, workspace_id, repo)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name cannot be empty")
    await repo._pool.execute(
        "UPDATE workspaces SET name = $1 WHERE id = $2",
        name, workspace_id,
    )
    return {"id": str(workspace_id), "name": name}


@router.get("/{workspace_id}/stats")
async def workspace_stats(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await _assert_workspace(user_id, workspace_id, repo)
    pool = repo._pool
    agent_count = await pool.fetchval(
        "SELECT COUNT(*) FROM agents WHERE workspace_id = $1", workspace_id
    )
    skill_count = await pool.fetchval(
        "SELECT COUNT(*) FROM agent_skills WHERE workspace_id = $1 AND active = TRUE",
        workspace_id,
    )
    execution_count = await pool.fetchval(
        "SELECT COUNT(*) FROM executions WHERE workspace_id = $1", workspace_id
    )
    member_count = await pool.fetchval(
        "SELECT COUNT(*) FROM workspace_members WHERE workspace_id = $1", workspace_id
    )
    ws_row = await pool.fetchrow(
        "SELECT name FROM workspaces WHERE id = $1", workspace_id
    )
    return {
        "id": str(workspace_id),
        "name": ws_row["name"] if ws_row else "",
        "agent_count": int(agent_count or 0),
        "skill_count": int(skill_count or 0),
        "execution_count": int(execution_count or 0),
        "member_count": int(member_count or 0),
    }


@router.get("/{workspace_id}/executions")
async def list_workspace_executions(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    limit: int = Query(40, ge=1, le=100),
) -> dict:
    await _assert_workspace(user_id, workspace_id, repo)
    rows = await repo.list_executions_for_workspace(workspace_id, limit=limit)
    return {
        "executions": [
            {
                "id": str(r["id"]),
                "agent_id": str(r["agent_id"]),
                "agent_name": r["agent_name"],
                "agent_template": r["agent_template"],
                "status": r["status"],
                "user_message": (r["user_message"] or "")[:500],
                "error": r["error"],
                "created_at": r["created_at"].isoformat(),
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
            }
            for r in rows
        ]
    }


@router.get("/{workspace_id}/members")
async def list_members(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await _assert_workspace(user_id, workspace_id, repo)
    members = await repo.list_workspace_members(workspace_id)
    return {
        "members": [
            {"user_id": str(m["id"]), "email": m["email"], "role": m["role"]}
            for m in members
        ]
    }


@router.post("/{workspace_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    workspace_id: UUID,
    body: AddMemberIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await _assert_admin(user_id, workspace_id, repo)
    if body.role not in ("admin", "editor", "viewer"):
        raise HTTPException(status_code=400, detail="role must be admin, editor, or viewer")
    target = await repo.get_user_by_email(body.email)
    if not target:
        raise HTTPException(status_code=404, detail="no account found for that email — they must register first")
    await repo.add_workspace_member(workspace_id, target["id"], body.role)
    return {"user_id": str(target["id"]), "email": target["email"], "role": body.role}


@router.delete("/{workspace_id}/members/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    workspace_id: UUID,
    target_user_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> None:
    await _assert_admin(user_id, workspace_id, repo)
    members = await repo.list_workspace_members(workspace_id)
    admins = [m for m in members if m["role"] == "admin"]
    target = next((m for m in members if str(m["id"]) == str(target_user_id)), None)
    if target and target["role"] == "admin" and len(admins) <= 1:
        raise HTTPException(status_code=403, detail="cannot remove the last admin")
    await repo.remove_workspace_member(workspace_id, target_user_id)
