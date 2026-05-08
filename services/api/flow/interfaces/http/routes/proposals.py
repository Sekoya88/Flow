from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from flow.application.genome_service import activate_genome
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo
from flow.interfaces.http.schemas import ProposalActionIn

router = APIRouter(prefix="/api/v1/proposals", tags=["proposals"])


async def _workspace_for_user(repo: FlowRepository, user_id: UUID) -> UUID:
    rows = await repo.list_workspaces_for_user(user_id)
    if not rows:
        raise HTTPException(status_code=400, detail="no workspace")
    return rows[0]["id"]


@router.get("")
async def list_proposals(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    status_filter: str | None = Query(None, alias="status"),
) -> dict:
    ws = await _workspace_for_user(repo, user_id)
    rows = await repo.list_proposals(ws, status=status_filter)
    return {
        "proposals": [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "body": r["body"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat(),
                **(
                    {"execution_id": str(r["execution_id"])}
                    if r.get("execution_id") is not None
                    else {}
                ),
            }
            for r in rows
        ]
    }


@router.post("/{proposal_id}/action")
async def act_on_proposal(
    proposal_id: UUID,
    body: ProposalActionIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws = await _workspace_for_user(repo, user_id)
    ok = await repo.set_proposal_status(proposal_id, ws, body.status)
    if not ok:
        raise HTTPException(status_code=404, detail="proposal not found")
    if body.status == "approved":
        version_row = await repo._pool.fetchrow(
            "SELECT id, agent_id FROM agent_versions "
            "WHERE proposal_id = $1 AND status = 'candidate'",
            proposal_id,
        )
        if version_row:
            await activate_genome(
                pool=repo._pool,
                version_id=version_row["id"],
                agent_id=version_row["agent_id"],
                workspace_id=ws,
            )
    return {"ok": True}
