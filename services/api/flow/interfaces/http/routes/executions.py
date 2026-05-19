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


@router.get("")
async def list_executions(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    rows = await repo.list_executions_for_user(user_id)
    return {
        "executions": [
            {
                "id": str(r["id"]),
                "status": r["status"],
                "agent_id": str(r["agent_id"]),
                "agent_name": r["agent_name"] or r["agent_template"],
                "user_message": r["user_message"],
                "answer": r["answer"],
                "thread_id": str(r["thread_id"]) if r["thread_id"] else str(r["id"]),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
            }
            for r in rows
        ]
    }


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    rows = await repo.list_executions_in_thread(thread_id, user_id)
    if not rows:
        raise HTTPException(status_code=404, detail="thread not found")
    return {
        "thread_id": str(thread_id),
        "executions": [
            {
                "id": str(r["id"]),
                "status": r["status"],
                "agent_id": str(r["agent_id"]),
                "agent_name": r["agent_name"] or r["agent_template"],
                "user_message": r["user_message"],
                "answer": r["answer"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/{execution_id}")
async def get_execution(
    execution_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    row = await repo.get_execution_for_user(execution_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="execution not found")
    events = await repo.list_events(execution_id)
    return {
        "id": str(row["id"]),
        "status": row["status"],
        "agent_id": str(row["agent_id"]),
        "agent_name": row["agent_name"] or row["agent_template"],
        "user_message": row["user_message"],
        "answer": row["answer"],
        "thread_id": str(row["thread_id"]) if row["thread_id"] else str(row["id"]),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "events": [
            {"id": e["id"], "kind": e["kind"], "payload": dict(e["payload"])}
            for e in events
        ],
    }


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
    await arq.enqueue_job(
        "task_run_deer_execution",
        str(execution_id),
        str(row["workspace_id"]),
        str(row["agent_id"]),
        str(user_id),
        "",  # user_message empty — state already has messages
    )

    return {"ok": True, "execution_id": str(execution_id)}
