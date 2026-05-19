"""Unauthenticated endpoints for the local desktop app (macOS menubar)."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/local", tags=["local"])


@router.get("/active-agents")
async def active_agents(request: Request) -> dict:
    """Return agent IDs that have had events in the last 2 hours. No auth required."""
    stream_hub = request.app.state.stream_hub
    ids = await stream_hub.get_active_agent_ids()
    return {"agents": [{"id": aid} for aid in ids]}
