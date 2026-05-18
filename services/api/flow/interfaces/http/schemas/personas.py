from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Inputs ────────────────────────────────────────────────────────────────────

class PersonaSaveIn(BaseModel):
    workspace_id: UUID
    content_md: str = Field(..., max_length=20_000)


class PersonaRegenerateIn(BaseModel):
    workspace_id: UUID


class QuestionnaireAnswer(BaseModel):
    question: str
    answer: str


class PersonaQuestionnaireIn(BaseModel):
    workspace_id: UUID
    answers: list[QuestionnaireAnswer]


# ── Outputs ───────────────────────────────────────────────────────────────────

class PersonaOut(BaseModel):
    id: UUID
    workspace_id: UUID
    user_id: UUID
    content_md: str
    version: int
    derived_from: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PersonaResponseOut(BaseModel):
    persona: PersonaOut | None
