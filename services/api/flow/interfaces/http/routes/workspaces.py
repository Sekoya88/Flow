from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


async def _assert_workspace(user_id: UUID, workspace_id: UUID, repo: FlowRepository) -> None:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if workspace_id not in allowed:
        raise HTTPException(status_code=403, detail="workspace not allowed")


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
