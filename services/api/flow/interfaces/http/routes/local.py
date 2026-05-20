"""Unauthenticated endpoints for the local desktop app (macOS menubar)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/local", tags=["local"])


@router.get("/active-agents")
async def active_agents(request: Request) -> dict:
    """Return agent IDs that have had events in the last 2 hours. No auth required."""
    stream_hub = request.app.state.stream_hub
    ids = await stream_hub.get_active_agent_ids()
    return {"agents": [{"id": aid} for aid in ids]}


@router.get("/agent-executions/{agent_id}")
async def agent_executions(agent_id: UUID, request: Request) -> dict:
    """Last 5 executions for an agent. No auth — local desktop only."""
    pool = request.app.state.pool
    rows = await pool.fetch(
        """
        SELECT id, status, user_message, created_at, completed_at
        FROM executions
        WHERE agent_id = $1
        ORDER BY created_at DESC
        LIMIT 5
        """,
        agent_id,
    )
    return {
        "executions": [
            {
                "id": str(r["id"]),
                "status": r["status"],
                "message": (r["user_message"] or "")[:60],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
            }
            for r in rows
        ]
    }


@router.get("/agent-memory/{agent_id}")
async def agent_memory(agent_id: UUID, request: Request) -> dict:
    """Last 10 memory entries for an agent. No auth — local desktop only."""
    pool = request.app.state.pool
    rows = await pool.fetch(
        """
        SELECT id, content, created_at
        FROM agent_memories
        WHERE agent_id = $1
        ORDER BY created_at DESC
        LIMIT 10
        """,
        agent_id,
    )
    return {
        "memories": [
            {
                "id": str(r["id"]),
                "content": r["content"][:120],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    }
