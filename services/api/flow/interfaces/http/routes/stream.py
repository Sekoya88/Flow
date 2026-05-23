from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo

router = APIRouter(prefix="/api/v1/stream", tags=["stream"])


async def _assert_workspace(user_id: UUID, workspace_id: UUID, repo: FlowRepository) -> None:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    if workspace_id not in {r["id"] for r in ws_rows}:
        raise HTTPException(status_code=403, detail="workspace not allowed")


@router.get("")
async def global_stream(
    request: Request,
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> StreamingResponse:
    """Server-sent events for all workspace activity (digest, knowledge ingest, executions)."""
    await _assert_workspace(user_id, workspace_id, repo)

    async def event_generator():
        async for event in request.app.state.stream_hub.subscribe_global(str(workspace_id)):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
