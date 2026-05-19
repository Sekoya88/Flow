from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── Inputs ────────────────────────────────────────────────────────────────────

class AnalyticsEventIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    props: dict[str, Any] = Field(default_factory=dict)


class AnalyticsBatchIn(BaseModel):
    events: list[AnalyticsEventIn] = Field(default_factory=list, max_length=100)


# ── Outputs ───────────────────────────────────────────────────────────────────

class AnalyticsEventOut(BaseModel):
    ok: bool
