from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Inputs ────────────────────────────────────────────────────────────────────

class MemoryCreateIn(BaseModel):
    workspace_id: UUID
    agent_id: UUID
    content: str = Field(min_length=1, max_length=16000)


# ── Outputs ───────────────────────────────────────────────────────────────────

class MemoryCreateOut(BaseModel):
    id: UUID


class EpisodicMemoryOut(BaseModel):
    id: UUID
    content: str
    execution_id: UUID | None
    created_at: datetime


class SemanticMemoryOut(BaseModel):
    id: UUID
    content: str
    created_at: datetime


class TieredMemoriesOut(BaseModel):
    episodic: list[EpisodicMemoryOut]
    semantic: list[SemanticMemoryOut]


class DeletedOut(BaseModel):
    deleted: bool
