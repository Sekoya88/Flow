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


class SkillVibeCreateIn(BaseModel):
    workspace_id: UUID
    agent_id: UUID
    prompt: str = Field(min_length=1, max_length=2000)
    category: str = "General"


class SkillVibeModifyIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)


# ── Outputs ───────────────────────────────────────────────────────────────────


class SkillOut(BaseModel):
    id: UUID
    name: str
    version: int
    content_md: str
    description: str = ""
    category: str = "General"
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
    category: str = "General"
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


# ── Training schemas ──────────────────────────────────────────────────────────


class TrainingConfigIn(BaseModel):
    agent_id: UUID
    workspace_id: UUID
    edit_budget: int = Field(default=5, ge=1, le=20)
    max_epochs: int = Field(default=3, ge=1, le=10)
    golden_set_id: UUID | None = None
    min_val_improvement: float = Field(default=0.02, ge=0.0, le=1.0)


class TrainingStartOut(BaseModel):
    run_id: str
    skill_id: str
    status: str


class TrainingEpochOut(BaseModel):
    epoch: int
    eval_score: float
    baseline_score: float
    accepted: bool
    patch_count: int
    created_at: str  # ISO format


class TrainingRunOut(BaseModel):
    id: str
    status: str
    epoch: int
    baseline_score: float | None
    best_score: float | None
    accepted: bool | None
    created_at: str  # ISO format


class TrainingRunsOut(BaseModel):
    runs: list[TrainingRunOut]


class TrainingRunDetailOut(BaseModel):
    id: str
    status: str
    epoch: int
    baseline_score: float | None
    best_score: float | None
    accepted: bool | None
    created_at: str
    epochs: list[TrainingEpochOut]
    patches_applied: int
    patches_rejected: int
