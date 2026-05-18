from __future__ import annotations

import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo
from flow.interfaces.http.schemas import ScheduleCreateIn, ScheduleToggleIn

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])


_SYSTEM_CRON_JOBS = [
    {
        "name": "scheduler_tick",
        "cron_expr": "* * * * *",
        "human_readable": "Every minute",
        "description": "Enqueues enabled agent schedules that are due",
    },
    {
        "name": "auto_eval_tick",
        "cron_expr": "0 3 * * *",
        "human_readable": "Every day at 3:00 AM UTC",
        "description": "Runs nightly golden set evaluation across all workspaces",
    },
    {
        "name": "skill_decay_tick",
        "cron_expr": "0 4 * * *",
        "human_readable": "Every day at 4:00 AM UTC",
        "description": "Decays active skill scores; prunes skills with low score and sufficient usage",
    },
    {
        "name": "persona_freshness_tick",
        "cron_expr": "30 3 * * *",
        "human_readable": "Every day at 3:30 AM UTC",
        "description": "Flags SOUL.md personas as stale when user preferences have changed since last regeneration",
    },
]


def _next_run_for(cron_expr: str) -> str:
    now = datetime.datetime.utcnow().replace(second=0, microsecond=0)
    if cron_expr == "* * * * *":
        nxt = now + datetime.timedelta(minutes=1)
    elif cron_expr in ("0 3 * * *", "0 4 * * *", "30 3 * * *"):
        hour = 3 if cron_expr in ("0 3 * * *", "30 3 * * *") else 4
        minute = 30 if cron_expr == "30 3 * * *" else 0
        candidate = now.replace(hour=hour, minute=minute)
        if candidate <= now:
            candidate += datetime.timedelta(days=1)
        nxt = candidate
    else:
        nxt = now + datetime.timedelta(minutes=1)
    return nxt.isoformat() + "Z"



@router.get("/cron-jobs")
async def list_cron_jobs(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> dict:
    """List system ARQ cron jobs with next scheduled run time."""
    return {
        "cron_jobs": [
            {**job, "next_run": _next_run_for(job["cron_expr"])}
            for job in _SYSTEM_CRON_JOBS
        ]
    }


@router.post("")
async def create_schedule(
    body: ScheduleCreateIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    agent = await repo.get_agent(body.agent_id, body.workspace_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    sid = await repo.create_agent_schedule(
        workspace_id=body.workspace_id,
        agent_id=body.agent_id,
        user_id=user_id,
        cron_expr=body.cron_expr,
        prompt_template=body.prompt_template,
        delivery_type=body.delivery_type,
        delivery_target=body.delivery_target,
    )
    return {"id": str(sid)}


@router.get("")
async def list_schedules(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    rows = await repo.list_agent_schedules(workspace_id, user_id)
    return {
        "schedules": [
            {
                "id": str(r["id"]),
                "agent_id": str(r["agent_id"]),
                "agent_name": r["agent_name"],
                "cron_expr": r["cron_expr"],
                "prompt_template": r["prompt_template"],
                "delivery_type": r["delivery_type"],
                "delivery_target": r["delivery_target"],
                "enabled": r["enabled"],
                "last_run_at": r["last_run_at"].isoformat() if r["last_run_at"] else None,
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


@router.patch("/{schedule_id}/toggle")
async def toggle_schedule(
    schedule_id: UUID,
    body: ScheduleToggleIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await repo.update_schedule_enabled(schedule_id, body.enabled)
    return {"enabled": body.enabled}


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: UUID,
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    deleted = await repo.delete_agent_schedule(schedule_id, workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="schedule not found")
    return {"deleted": True}
