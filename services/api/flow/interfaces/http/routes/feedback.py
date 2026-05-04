from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from flow.application.curator import maybe_spawn_proposal
from flow.config import Settings, get_settings
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo
from flow.interfaces.http.schemas import FeedbackIn

router = APIRouter(prefix="/api/v1/executions", tags=["feedback"])

NEGATIVE_SCORE_THRESHOLD = 0.5


async def _maybe_insert_negative(
    *,
    repo: FlowRepository,
    execution_id: UUID,
    workspace_id: UUID,
    agent_id: UUID,
    user_message: str,
    score: float,
) -> None:
    if score >= NEGATIVE_SCORE_THRESHOLD:
        return
    content = f"Query: {user_message[:300]}\n[rated {score:.0%} — poor quality]"
    await repo.insert_agent_negative(workspace_id, agent_id, content, source="feedback")


@router.post("/{execution_id}/feedback")
async def post_feedback(
    execution_id: UUID,
    body: FeedbackIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    row = await repo.get_execution_for_user(execution_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="execution not found")
    await repo.upsert_feedback(execution_id, user_id, body.score, body.comment)
    wid = row["workspace_id"]
    pid = await maybe_spawn_proposal(
        repo=repo,
        workspace_id=wid,
        agent_id=row["agent_id"],
        user_id=user_id,
        execution_id=execution_id,
        score=body.score,
        openai_api_key=settings.openai_api_key,
    )
    await _maybe_insert_negative(
        repo=repo,
        execution_id=execution_id,
        workspace_id=wid,
        agent_id=row["agent_id"],
        user_message=row["user_message"] or "",
        score=body.score,
    )
    return {"ok": True, "proposal_id": str(pid) if pid else None}
