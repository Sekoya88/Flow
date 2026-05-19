from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ── Inputs ────────────────────────────────────────────────────────────────────


class PreferenceUpsertIn(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    value: dict


class PreferenceCreateIn(BaseModel):
    workspace_id: UUID
    agent_id: UUID | None = None
    class_: str = Field(alias="class")
    value: str = Field(min_length=1, max_length=200)
    status: str = "active"

    model_config = {"populate_by_name": True}


class PreferencePatchIn(BaseModel):
    action: str  # promote | pin | unpin | forget | veto


class OnboardingAnswerIn(BaseModel):
    class_: str = Field(alias="class")
    value: str

    model_config = {"populate_by_name": True}


class OnboardingAnswersIn(BaseModel):
    answers: list[OnboardingAnswerIn]


# ── Outputs ───────────────────────────────────────────────────────────────────


class PreferenceOut(BaseModel):
    id: UUID
    class_: str = Field(alias="class")
    value: str
    score: float
    status: str
    pinned: bool
    agent_id: UUID | None
    last_reinforced_at: datetime
    created_at: datetime

    model_config = {"populate_by_name": True}


class PreferenceListOut(BaseModel):
    global_: list[PreferenceOut] = Field(alias="global")
    agent_specific: list[PreferenceOut]

    model_config = {"populate_by_name": True}


class PreferenceCreateOut(BaseModel):
    id: UUID
    class_: str = Field(alias="class")
    value: str
    status: str

    model_config = {"populate_by_name": True}


class OnboardingOut(BaseModel):
    created: int
