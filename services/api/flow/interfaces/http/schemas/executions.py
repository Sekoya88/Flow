from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ExecutionItemOut(BaseModel):
    id: UUID
    status: str
    agent_id: UUID
    agent_name: str | None
    user_message: str
    answer: str | None
    thread_id: UUID
    created_at: datetime | None
    completed_at: datetime | None = None


class ExecutionListOut(BaseModel):
    executions: list[ExecutionItemOut]


class ExecutionEventOut(BaseModel):
    id: int
    kind: str
    payload: dict[str, Any]


class ExecutionDetailOut(ExecutionItemOut):
    events: list[ExecutionEventOut]


class ThreadOut(BaseModel):
    thread_id: UUID
    executions: list[ExecutionItemOut]


class StreamTokenOut(BaseModel):
    stream_jwt: str


class ApproveOut(BaseModel):
    ok: bool
    execution_id: UUID
