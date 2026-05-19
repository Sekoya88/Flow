from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

# ── Inputs ────────────────────────────────────────────────────────────────────


class FeedbackIn(BaseModel):
    score: float = Field(ge=0, le=1)
    comment: str | None = None


# ── Outputs ───────────────────────────────────────────────────────────────────


class FeedbackOut(BaseModel):
    ok: bool
    proposal_id: UUID | None = None
