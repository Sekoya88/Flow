"""Scheduler tick — runs every minute via ARQ cron, enqueues due agent schedules."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def is_schedule_due(cron_expr: str, last_run_at: datetime | None) -> bool:
    """Return True if this schedule should fire on the current tick."""
    try:
        from croniter import croniter
        now = datetime.now(UTC)
        if last_run_at is None:
            return True
        it = croniter(cron_expr, last_run_at)
        next_run = it.get_next(datetime)
        return next_run <= now
    except Exception as exc:
        logger.warning("croniter error for %r: %s", cron_expr, exc)
        return False


async def scheduler_tick(ctx: dict[str, Any]) -> dict:
    """ARQ cron job: check all enabled schedules and enqueue due ones."""
    pool = ctx.get("pool")
    if pool is None:
        logger.warning("scheduler_tick: no pool in ctx")
        return {"enqueued": 0}

    from flow.infrastructure.persistence.repo import FlowRepository
    repo = FlowRepository(pool)
    schedules = await repo.list_enabled_schedules()

    enqueued = 0
    redis = ctx.get("redis")
    for sched in schedules:
        if not is_schedule_due(sched["cron_expr"], sched["last_run_at"]):
            continue
        await repo.update_schedule_last_run(sched["id"])
        if redis is not None:
            await redis.enqueue_job(
                "run_deer_execution",
                agent_id=str(sched["agent_id"]),
                workspace_id=str(sched["workspace_id"]),
                user_id=str(sched["user_id"]),
                user_message=sched["prompt_template"],
                schedule_id=str(sched["id"]),
            )
            enqueued += 1
            logger.info(
                "scheduler_tick: enqueued run",
                extra={"agent_id": str(sched["agent_id"]), "schedule_id": str(sched["id"])},
            )

    return {"enqueued": enqueued}
