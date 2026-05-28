"""Observability logs: rich execution history with event summaries + LangSmith status."""

from __future__ import annotations

import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from flow.config import get_settings
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


@router.get("/status")
async def observability_status() -> dict:
    """Return LangSmith connection status and config for the frontend banner."""
    settings = get_settings()
    api_key = (settings.langsmith_api_key or "").strip() or os.getenv("LANGSMITH_API_KEY", "").strip() or os.getenv("LANGCHAIN_API_KEY", "").strip()
    enabled = bool(api_key) and settings.langsmith_tracing
    project = settings.langsmith_project or "flow-local"
    trace_url = f"https://smith.langchain.com/o/projects?filter=eq(name%2C%22{project}%22)" if enabled else None
    return {
        "langsmith_enabled": enabled,
        "project": project if enabled else None,
        "trace_url": trace_url,
        "log_level": settings.log_level,
        "log_json": settings.log_json,
    }


@router.get("")
async def list_logs(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    limit: int = Query(50, ge=1, le=200),
    agent_id: UUID | None = Query(None),
    status: str | None = Query(None),
) -> dict:
    """Return recent executions with event-level summaries (LLM calls, tool calls, tokens, duration)."""
    ws_rows = await repo.list_workspaces_for_user(user_id)
    if not ws_rows:
        return {"executions": []}
    ws_id = ws_rows[0]["id"]

    agent_filter = "AND e.agent_id = $3" if agent_id else ""
    status_filter = "AND e.status = $4" if status else ""

    params: list = [ws_id, limit]
    if agent_id:
        params.append(agent_id)
    if status:
        params.append(status)

    rows = await repo._pool.fetch(
        f"""
        SELECT
            e.id, e.agent_id, e.status, e.error,
            LEFT(e.user_message, 200) AS user_message,
            e.created_at, e.completed_at,
            a.name AS agent_name, a.template AS agent_template,
            EXTRACT(EPOCH FROM (e.completed_at - e.created_at)) * 1000 AS duration_ms,
            (SELECT COUNT(*) FROM execution_events ee WHERE ee.execution_id = e.id AND ee.kind = 'node_update') AS node_count,
            (SELECT COUNT(*) FROM execution_events ee WHERE ee.execution_id = e.id AND ee.kind = 'tool_call') AS tool_count,
            (SELECT COUNT(*) FROM execution_events ee WHERE ee.execution_id = e.id AND ee.kind IN ('llm.start','llm_start')) AS llm_count,
            (SELECT SUM((ee.payload->>'prompt_tokens')::int + (ee.payload->>'completion_tokens')::int)
             FROM execution_events ee
             WHERE ee.execution_id = e.id AND ee.payload->>'prompt_tokens' IS NOT NULL) AS total_tokens,
            (SELECT ee.payload->>'answer'
             FROM execution_events ee
             WHERE ee.execution_id = e.id AND ee.kind = 'final'
             LIMIT 1) AS answer
        FROM executions e
        JOIN agents a ON a.id = e.agent_id
        WHERE e.workspace_id = $1
          {agent_filter}
          {status_filter}
        ORDER BY e.created_at DESC
        LIMIT $2
        """,
        *params,
    )

    return {
        "executions": [
            {
                "id": str(r["id"]),
                "agent_id": str(r["agent_id"]),
                "agent_name": r["agent_name"] or r["agent_template"],
                "agent_template": r["agent_template"],
                "status": r["status"],
                "error": r["error"],
                "user_message": r["user_message"] or "",
                "answer": (r["answer"] or "")[:300],
                "created_at": r["created_at"].isoformat(),
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
                "duration_ms": int(r["duration_ms"]) if r["duration_ms"] is not None else None,
                "node_count": int(r["node_count"] or 0),
                "tool_count": int(r["tool_count"] or 0),
                "llm_count": int(r["llm_count"] or 0),
                "total_tokens": int(r["total_tokens"]) if r["total_tokens"] is not None else None,
            }
            for r in rows
        ]
    }


@router.get("/training")
async def list_training_logs(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    limit: int = Query(50, ge=1, le=200),
    skill_id: UUID | None = Query(None),
) -> dict:
    """Return recent skill training runs."""
    ws_rows = await repo.list_workspaces_for_user(user_id)
    if not ws_rows:
        return {"runs": []}
    ws_id = ws_rows[0]["id"]

    skill_filter = "AND str.skill_id = $3" if skill_id else ""
    params: list = [ws_id, limit]
    if skill_id:
        params.append(skill_id)

    rows = await repo._pool.fetch(
        f"""
        SELECT
            str.id,
            str.skill_id,
            s.name AS skill_name,
            str.status,
            str.best_score,
            str.epoch,
            str.error_message,
            str.created_at,
            str.completed_at,
            COALESCE(EXTRACT(EPOCH FROM (str.completed_at - str.created_at)) * 1000, 0) AS duration_ms
        FROM skill_training_runs str
        JOIN agent_skills s ON s.id = str.skill_id
        JOIN agents a ON a.id = s.agent_id
        WHERE a.workspace_id = $1
          {skill_filter}
        ORDER BY str.created_at DESC
        LIMIT $2
        """,
        *params,
    )

    return {
        "runs": [
            {
                "id": str(r["id"]),
                "skill_id": str(r["skill_id"]),
                "skill_name": r["skill_name"] or "unknown",
                "status": r["status"],
                "best_score": float(r["best_score"]) if r["best_score"] is not None else None,
                "epoch": r["epoch"],
                "error_message": r["error_message"],
                "created_at": r["created_at"].isoformat(),
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
                "duration_ms": int(r["duration_ms"]) if r["duration_ms"] is not None else 0,
            }
            for r in rows
        ]
    }


@router.get("/research")
async def list_research_logs(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """Return recent research digest runs."""
    ws_rows = await repo.list_workspaces_for_user(user_id)
    if not ws_rows:
        return {"runs": []}
    ws_id = ws_rows[0]["id"]

    rows = await repo.list_digest_runs(ws_id, limit=limit)

    return {
        "runs": [
            {
                "id": str(r["id"]),
                "status": r["status"],
                "source": r["source"],
                "paper_count": r["paper_count"],
                "error": r["error"],
                "started_at": r["started_at"].isoformat(),
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
                "duration_ms": int(r["duration_ms"]) if r["duration_ms"] is not None else 0,
            }
            for r in rows
        ]
    }


@router.get("/{execution_id}")
async def get_log_detail(
    execution_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Full execution log: all events in chronological order with structured payloads."""
    row = await repo.get_execution_for_user(execution_id, user_id)
    if not row:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="execution not found")

    events = await repo.list_events(execution_id)

    # Fetch skills used in this execution
    skill_rows = await repo._pool.fetch(
        """
        SELECT see.skill_id, s.name AS skill_name, see.matched_text, see.created_at
        FROM skill_execution_events see
        JOIN agent_skills s ON s.id = see.skill_id
        WHERE see.execution_id = $1
        ORDER BY see.created_at
        """,
        execution_id,
    )
    skills_used = [
        {
            "skill_id": str(r["skill_id"]),
            "skill_name": r["skill_name"],
            "matched_text": r["matched_text"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in skill_rows
    ]

    # Build structured timeline
    timeline = []
    for ev in events:
        payload = dict(ev["payload"]) if isinstance(ev["payload"], dict) else {}
        entry: dict = {
            "id": ev["id"],
            "kind": ev["kind"],
            "created_at": ev["created_at"].isoformat(),
            "payload": payload,
        }
        # Surface key fields for easy rendering
        if ev["kind"] == "node_update":
            entry["node"] = payload.get("node", "unknown")
        elif ev["kind"] == "tool_call":
            entry["tool"] = payload.get("tool", "unknown")
            entry["duration_ms"] = payload.get("duration_ms")
            entry["status"] = payload.get("status", "success")
        elif ev["kind"] in ("llm.start", "llm_start"):
            entry["model"] = payload.get("model", "unknown")
        elif ev["kind"] in ("llm.end", "llm_end"):
            entry["latency_ms"] = payload.get("latency_ms")
            entry["prompt_tokens"] = payload.get("prompt_tokens")
            entry["completion_tokens"] = payload.get("completion_tokens")
        elif ev["kind"] == "final":
            entry["answer"] = (payload.get("answer") or "")[:500]
            entry["confidence"] = payload.get("confidence")
        elif ev["kind"] == "error":
            entry["message"] = payload.get("message", "unknown error")
        timeline.append(entry)

    duration_ms = None
    if row["created_at"] and row["completed_at"]:
        duration_ms = int((row["completed_at"] - row["created_at"]).total_seconds() * 1000)

    return {
        "id": str(row["id"]),
        "agent_id": str(row["agent_id"]),
        "agent_name": row["agent_name"] or row["agent_template"],
        "status": row["status"],
        "error": row["error"],
        "user_message": row["user_message"] or "",
        "created_at": row["created_at"].isoformat(),
        "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        "duration_ms": duration_ms,
        "timeline": timeline,
        "skills_used": skills_used,
    }
