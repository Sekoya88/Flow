from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

# ── Inputs ────────────────────────────────────────────────────────────────────

class ProposalActionIn(BaseModel):
    status: Literal["approved", "rejected"]


# ── Outputs ───────────────────────────────────────────────────────────────────

class ProposalOut(BaseModel):
    id: UUID
    title: str
    body: str
    status: str
    created_at: datetime
    auto_approved: bool = False
    execution_id: UUID | None = None


class ProposalListOut(BaseModel):
    proposals: list[ProposalOut]


class ProposalActionOut(BaseModel):
    ok: bool
