from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

# ── Inputs ────────────────────────────────────────────────────────────────────


class ABTestCreateIn(BaseModel):
    golden_set_id: UUID
    agent_a_id: UUID
    agent_a_version: str = ""
    agent_b_id: UUID
    agent_b_version: str = ""


# ── Outputs ───────────────────────────────────────────────────────────────────


class ABTestResultItem(BaseModel):
    item_id: UUID
    input_text: str
    agent_a_output: str | None
    agent_b_output: str | None
    winner: str | None  # "a" | "b" | "tie"
    reasoning: str | None


class ABTestOut(BaseModel):
    id: UUID
    golden_set_id: UUID
    agent_a_id: UUID
    agent_b_id: UUID
    status: str
    created_at: datetime
    results: list[ABTestResultItem] = []
