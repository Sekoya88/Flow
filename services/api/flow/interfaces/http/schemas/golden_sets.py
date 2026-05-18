from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# ── Inputs ────────────────────────────────────────────────────────────────────

class GoldenSetCreateIn(BaseModel):
    name: str
    description: str = ""


class GoldenSetItemCreateIn(BaseModel):
    input_text: str
    expected_output: str
    scoring_criteria: str = ""


class GoldenSetEvaluateIn(BaseModel):
    agent_id: UUID
    agent_version_label: str = ""


# ── Outputs ───────────────────────────────────────────────────────────────────

class GoldenSetOut(BaseModel):
    id: UUID
    name: str
    description: str
    item_count: int
    created_at: datetime


class GoldenSetListOut(BaseModel):
    sets: list[GoldenSetOut]


class GoldenSetItemOut(BaseModel):
    id: UUID
    input_text: str
    expected_output: str
    scoring_criteria: str
    created_at: datetime


class GoldenSetItemListOut(BaseModel):
    items: list[GoldenSetItemOut]


class EvaluationResultOut(BaseModel):
    id: UUID
    golden_set_id: UUID
    agent_id: UUID
    agent_version_label: str
    status: str
    score: float | None
    created_at: datetime
