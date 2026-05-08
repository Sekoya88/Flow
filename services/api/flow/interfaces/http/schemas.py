from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AgentCreateIn(BaseModel):
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=200)
    template: str = "deer_flow"
    config: dict[str, Any] = Field(default_factory=dict)


class AgentToolsPatchIn(BaseModel):
    """Partial tool toggles merged into agents.config.tools (see deer_graph)."""

    retrieve: bool | None = None
    sandbox: bool | None = None
    long_term_memory: bool | None = None


class AgentPatchIn(BaseModel):
    """Partial agent update: display name, system prompt, and/or tool toggles."""

    name: str | None = Field(None, min_length=1, max_length=200)
    system_prompt: str | None = None
    retrieve: bool | None = None
    sandbox: bool | None = None
    long_term_memory: bool | None = None
    tavily_search: bool | None = None
    fetch_webpage: bool | None = None
    arxiv_search: bool | None = None
    hf_papers: bool | None = None


class AnalyticsEventIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    props: dict[str, Any] = Field(default_factory=dict)


class AnalyticsBatchIn(BaseModel):
    events: list[AnalyticsEventIn] = Field(default_factory=list, max_length=100)


class ExecuteIn(BaseModel):
    message: str = Field(min_length=1, max_length=32000)


class KnowledgeCreateIn(BaseModel):
    workspace_id: UUID
    title: str
    body: str


class PreferenceUpsertIn(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    value: dict[str, Any]


class FeedbackIn(BaseModel):
    score: float = Field(ge=0, le=1)
    comment: str | None = None


class ProposalActionIn(BaseModel):
    status: Literal["approved", "rejected"]


class VibeIn(BaseModel):
    description: str = Field(min_length=10, max_length=2000)
