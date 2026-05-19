from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

# ── Inputs ────────────────────────────────────────────────────────────────────

class SkillCreateIn(BaseModel):
    workspace_id: UUID
    agent_id: UUID
    name: str = Field(min_length=1, max_length=200)
    content_md: str = Field(min_length=1, max_length=10000)


class SkillTestIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


# ── Outputs ───────────────────────────────────────────────────────────────────

class SkillOut(BaseModel):
    id: UUID
    name: str
    version: int
    content_md: str
    description: str = ""
    allowed_tools: list[str] = []
    triggers: list[str] = []
    metadata: dict[str, Any] = {}
    active: bool = True
    score: float = 1.0
    use_count: int = 0
    created_at: datetime


class SkillListOut(BaseModel):
    skills: list[SkillOut]


class SkillCreateOut(BaseModel):
    id: UUID


class SkillVersionOut(BaseModel):
    id: UUID
    version: int
    content_md: str
    active: bool
    created_at: datetime


class SkillHistoryOut(BaseModel):
    versions: list[SkillVersionOut]


class SkillActivateOut(BaseModel):
    id: UUID
    name: str
    version: int
    active: bool


class SkillImproveOut(BaseModel):
    improved: bool
    reason: str | None = None
    confidence: float
    candidate_skill_id: UUID | None = None
    proposal_id: UUID | None = None
    changelog: list[str] = []
    failure_analysis: str | None = None


class SkillUsageDataPoint(BaseModel):
    date: str
    count: int


class SkillUsageOut(BaseModel):
    skill_id: UUID
    window_days: int
    data: list[SkillUsageDataPoint]


class SkillCatalogItemOut(BaseModel):
    id: UUID
    agent_id: UUID
    agent_name: str | None
    name: str
    version: int
    description: str
    triggers: list[str]
    allowed_tools: list[str]
    metadata: dict[str, Any]
    score: float
    use_count: int
    created_at: datetime


class SkillCatalogOut(BaseModel):
    skills: list[SkillCatalogItemOut]


class DeactivateOut(BaseModel):
    deactivated: bool
