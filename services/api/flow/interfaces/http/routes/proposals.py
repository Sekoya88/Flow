from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)

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

    async with repo._pool.acquire() as conn:
        async with conn.transaction():
            updated = await conn.fetchrow(
                "UPDATE proposals SET status = $3 "
                "WHERE id = $1 AND workspace_id = $2 RETURNING id",
                proposal_id, ws, body.status,
            )
            if not updated:
                raise HTTPException(status_code=404, detail="proposal not found")

            if body.status == "approved":
                # Check for a skill-improvement candidate embedded in the proposal body
                proposal_rec = await conn.fetchrow(
                    "SELECT body FROM proposals WHERE id = $1", proposal_id
                )
                if proposal_rec:
                    import json as _json
                    try:
                        meta = _json.loads(proposal_rec["body"]) if proposal_rec["body"].strip().startswith("{") else {}
                    except Exception:
                        meta = {}
                    skill_candidate_id = meta.get("skill_candidate_id")
                    if skill_candidate_id:
                        from uuid import UUID as _UUID
                        sid = _UUID(skill_candidate_id)
                        sibling = await conn.fetchrow(
                            "SELECT agent_id, name FROM agent_skills WHERE id = $1 AND workspace_id = $2",
                            sid, ws,
                        )
                        if sibling:
                            await conn.execute(
                                "UPDATE agent_skills SET active = false "
                                "WHERE agent_id = $1 AND name = $2 AND active = true",
                                sibling["agent_id"], sibling["name"],
                            )
                            await conn.execute(
                                "UPDATE agent_skills SET active = true WHERE id = $1",
                                sid,
                            )
                            logger.info(
                                "skill.activated_via_proposal",
                                extra={
                                    "proposal_id": str(proposal_id),
                                    "skill_id": str(sid),
                                },
                            )

                version_row = await conn.fetchrow(
                    "SELECT av.id, av.agent_id FROM agent_versions av "
                    "JOIN agents a ON a.id = av.agent_id "
                    "WHERE av.proposal_id = $1 AND av.status = 'candidate' AND a.workspace_id = $2",
                    proposal_id, ws,
                )
                if version_row:
                    await conn.execute(
                        "UPDATE agent_versions SET status = 'archived' "
                        "WHERE agent_id = $1 AND status = 'active' "
                        "AND EXISTS (SELECT 1 FROM agents WHERE id = $1 AND workspace_id = $2)",
                        version_row["agent_id"], ws,
                    )
                    snap = await conn.fetchrow(
                        "UPDATE agent_versions SET status = 'active' "
                        "WHERE id = $1 AND agent_id = $2 RETURNING config_snapshot, template",
                        version_row["id"], version_row["agent_id"],
                    )
                    if snap:
                        await conn.execute(
                            "UPDATE agents SET config = $1, template = $2 "
                            "WHERE id = $3 AND workspace_id = $4",
                            snap["config_snapshot"], snap["template"],
                            version_row["agent_id"], ws,
                        )
                        logger.info(
                            "genome.activated_via_proposal",
                            extra={
                                "proposal_id": str(proposal_id),
                                "version_id": str(version_row["id"]),
                                "agent_id": str(version_row["agent_id"]),
                            },
                        )

    return {"ok": True}
