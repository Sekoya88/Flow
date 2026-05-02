from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from flow.config import Settings
from flow.infrastructure.auth.jwt_utils import create_stream_token
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo, get_settings_dep, get_stream_sse_user

router = APIRouter(prefix="/api/v1/executions", tags=["executions"])


@router.post("/{execution_id}/stream-token")
async def mint_stream_token(
    execution_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> dict[str, str]:
    """Mint a short-lived JWT for GET .../stream?stream_jwt= (avoids putting the session JWT in query logs)."""
    row = await repo.get_execution_for_user(execution_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="execution not found")
    token = create_stream_token(
        secret=settings.jwt_secret, sub=user_id, execution_id=execution_id, ttl_seconds=120
    )
    return {"stream_jwt": token}


@router.get("/{execution_id}/stream")
async def stream_execution(
    request: Request,
    execution_id: UUID,
    user_id: Annotated[UUID, Depends(get_stream_sse_user)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> StreamingResponse:
    row = await repo.get_execution_for_user(execution_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="execution not found")

    async def event_generator():
        last_id = int(request.headers.get("last-event-id", "0"))

        backfill = await repo.get_execution_events(execution_id, after_id=last_id)
        for ev in backfill:
            data = json.dumps({"kind": ev["kind"], **ev["payload"]})
            yield f"id: {ev['id']}\ndata: {data}\n\n"
            if ev["kind"] == "done":
                return

        async for event in request.app.state.stream_hub.subscribe(execution_id):
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("kind") == "done":
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/{execution_id}/approve")
async def approve_execution(
    request: Request,
    execution_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Resume a human-in-loop execution that is waiting for approval.

    Sets approved=True in graph state and re-invokes the graph so it can
    pass the human_gate and continue execution.
    """
    row = await repo.get_execution_for_user(execution_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="execution not found")
    if row["status"] != "running":
        raise HTTPException(status_code=409, detail="execution is not in running state")

    checkpointer = request.app.state.checkpointer
    config = {"configurable": {"thread_id": str(execution_id)}}

    # Patch state: set approved=True so human_gate condition passes
    await checkpointer.aput(config, {"approved": True}, {}, {})

    # Re-enqueue so the worker picks up and resumes from the interrupt point
    from flow.infrastructure.queue.client import get_arq_pool
    arq = await get_arq_pool()
    raw_cfg = row["agent_config"]
    agent_config = dict(raw_cfg) if isinstance(raw_cfg, dict) else {}
    await arq.enqueue_job(
        "run_deer_execution",
        str(execution_id),
        str(row["workspace_id"]),
        str(row["agent_id"]),
        str(user_id),
        "",  # user_message empty — state already has messages
        agent_config,
    )

    return {"ok": True, "execution_id": str(execution_id)}
