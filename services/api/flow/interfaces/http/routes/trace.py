from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo

router = APIRouter(prefix="/api/v1/executions", tags=["trace"])


@router.get("/{execution_id}/trace")
async def get_execution_trace(
    execution_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    row = await repo.get_execution_for_user(execution_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="execution not found")

    events = await repo.list_events(execution_id)
    if not events:
        return {"nodes": [], "tool_calls": [], "total_duration_ms": None, "started_at": None}

    node_completions: list[dict] = []
    tool_calls: list[dict] = []
    first_ts = None
    last_ts = None

    for ev in events:
        ts = ev["created_at"]
        if first_ts is None:
            first_ts = ts
        last_ts = ts

        kind = ev["kind"]
        payload = ev["payload"] if isinstance(ev["payload"], dict) else {}

        if kind == "node_update":
            node_name = payload.get("node", "unknown")
            node_completions.append({"name": node_name, "ended_at": ts})

        elif kind == "tool_call":
            tool_calls.append({
                "tool": payload.get("tool", "unknown"),
                "duration_ms": payload.get("duration_ms", 0),
                "status": payload.get("status", "success"),
                "input": payload.get("input", {}),
                "output": str(payload.get("output", ""))[:500],
            })

    # Build node spans: each node starts where the previous ended (first starts at first_ts)
    nodes = []
    prev_ts = first_ts
    for nc in node_completions:
        started_at = prev_ts
        ended_at = nc["ended_at"]
        if started_at and ended_at and ended_at >= started_at:
            duration_ms = int((ended_at - started_at).total_seconds() * 1000)
        else:
            duration_ms = None
        nodes.append({
            "name": nc["name"],
            "started_at": started_at.isoformat() if started_at else None,
            "ended_at": ended_at.isoformat() if ended_at else None,
            "duration_ms": duration_ms,
        })
        prev_ts = ended_at

    total_duration_ms = (
        int((last_ts - first_ts).total_seconds() * 1000)
        if first_ts and last_ts
        else None
    )

    return {
        "nodes": nodes,
        "tool_calls": tool_calls,
        "total_duration_ms": total_duration_ms,
        "started_at": first_ts.isoformat() if first_ts else None,
    }
