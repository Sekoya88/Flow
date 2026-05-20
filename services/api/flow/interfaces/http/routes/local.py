"""Unauthenticated endpoints for the local desktop app (macOS menubar)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/local", tags=["local"])


@router.get("/agents")
async def list_agents(request: Request) -> dict:
    """All agents for the agent picker. No auth — local desktop only."""
    pool = request.app.state.pool
    rows = await pool.fetch("SELECT id, name FROM agents ORDER BY name")
    return {"agents": [{"id": str(r["id"]), "name": r["name"]} for r in rows]}


@router.get("/active-agents")
async def active_agents(request: Request) -> dict:
    """Return active agents (Redis), falling back to most-recent-execution agent from DB."""
    stream_hub = request.app.state.stream_hub
    ids = await stream_hub.get_active_agent_ids()
    if ids:
        return {"agents": [{"id": aid, "name": None} for aid in ids]}
    pool = request.app.state.pool
    row = await pool.fetchrow(
        "SELECT a.id, a.name FROM executions e "
        "JOIN agents a ON a.id = e.agent_id "
        "ORDER BY e.created_at DESC LIMIT 1"
    )
    if row:
        return {"agents": [{"id": str(row["id"]), "name": row["name"]}]}
    return {"agents": []}


@router.get("/agent-executions/{agent_id}")
async def agent_executions(agent_id: UUID, request: Request) -> dict:
    """Last 10 executions for an agent. No auth — local desktop only."""
    pool = request.app.state.pool
    rows = await pool.fetch(
        """
        SELECT id, status, user_message, created_at, completed_at
        FROM executions
        WHERE agent_id = $1
        ORDER BY created_at DESC
        LIMIT 10
        """,
        agent_id,
    )
    return {
        "executions": [
            {
                "id": str(r["id"]),
                "status": r["status"],
                "message": (r["user_message"] or "")[:120],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
            }
            for r in rows
        ]
    }


@router.get("/agent-memory/{agent_id}")
async def agent_memory(agent_id: UUID, request: Request) -> dict:
    """Last 20 memory entries for an agent. No auth — local desktop only."""
    pool = request.app.state.pool
    rows = await pool.fetch(
        """
        SELECT id, content, created_at
        FROM agent_memories
        WHERE agent_id = $1
        ORDER BY created_at DESC
        LIMIT 20
        """,
        agent_id,
    )
    return {
        "memories": [
            {
                "id": str(r["id"]),
                "content": r["content"][:240],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    }


@router.get("/agent-skills/{agent_id}")
async def agent_skills(agent_id: UUID, request: Request) -> dict:
    """Top skills with bandit scores for the skill graph. No auth — local desktop only."""
    pool = request.app.state.pool
    rows = await pool.fetch(
        """
        SELECT s.id, s.name, s.use_count,
               COALESCE(
                   CASE WHEN b.total_pulls > 0 THEN b.total_reward / b.total_pulls ELSE NULL END,
                   s.score
               ) AS bandit_score
        FROM agent_skills s
        LEFT JOIN skill_bandit_arms b ON b.skill_id = s.id AND b.agent_id = $1
        WHERE s.agent_id = $1 AND s.active = true
        ORDER BY bandit_score DESC
        LIMIT 12
        """,
        agent_id,
    )
    return {
        "skills": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "score": round(float(r["bandit_score"]), 3),
                "use_count": r["use_count"],
            }
            for r in rows
        ]
    }
