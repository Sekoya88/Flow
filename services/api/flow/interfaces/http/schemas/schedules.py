from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ── Inputs ────────────────────────────────────────────────────────────────────


class ScheduleCreateIn(BaseModel):
    workspace_id: UUID
    agent_id: UUID
    cron_expr: str = Field(default="0 8 * * *", max_length=100)
    prompt_template: str = Field(
        default="Summarize the latest AI research papers from today.",
        max_length=4000,
    )
    delivery_type: str = Field(default="none")
    delivery_target: str | None = None


class ScheduleToggleIn(BaseModel):
    enabled: bool


# ── Outputs ───────────────────────────────────────────────────────────────────


class ScheduleOut(BaseModel):
    id: UUID
    workspace_id: UUID
    agent_id: UUID
    cron_expr: str
    prompt_template: str
    delivery_type: str
    delivery_target: str | None
    enabled: bool
    created_at: datetime


class ScheduleListOut(BaseModel):
    schedules: list[ScheduleOut]


class CronJobOut(BaseModel):
    name: str
    cron_expr: str
    human_readable: str
    description: str
    next_run: str


class CronJobListOut(BaseModel):
    jobs: list[CronJobOut]
