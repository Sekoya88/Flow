from __future__ import annotations

from pydantic import BaseModel

# ── Inputs ────────────────────────────────────────────────────────────────────

class PositionUpdateIn(BaseModel):
    x: float
    y: float
