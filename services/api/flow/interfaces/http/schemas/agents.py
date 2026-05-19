from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

# ── Inputs ────────────────────────────────────────────────────────────────────


class AgentCreateIn(BaseModel):
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=200)
    template: str = "deer_flow"
    config: dict[str, Any] = Field(default_factory=dict)


class AgentToolsPatchIn(BaseModel):
    """Partial tool toggles merged into agents.config.tools."""

    retrieve: bool | None = None
    sandbox: bool | None = None
    long_term_memory: bool | None = None


class AgentPatchIn(BaseModel):
    """Partial agent update: name, system prompt, tool toggles, autonomous mode."""

    name: str | None = Field(None, min_length=1, max_length=200)
    system_prompt: str | None = Field(default=None, min_length=1)
    retrieve: bool | None = None
    sandbox: bool | None = None
    long_term_memory: bool | None = None
    tavily_search: bool | None = None
    fetch_webpage: bool | None = None
    arxiv_search: bool | None = None
    hf_papers: bool | None = None
    auto_improve_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    auto_improve_rollback_delta: float | None = Field(default=None, ge=0.0, le=1.0)


class VibeIn(BaseModel):
    description: str = Field(min_length=10, max_length=2000)


class ExecuteIn(BaseModel):
    message: str = Field(min_length=1, max_length=32000)
    parent_execution_id: UUID | None = None


# ── Outputs ───────────────────────────────────────────────────────────────────


class AgentCreateOut(BaseModel):
    id: UUID


class AgentOut(BaseModel):
    id: UUID
    name: str
    template: str
    config: dict[str, Any]
    created_at: datetime


class AgentListOut(BaseModel):
    agents: list[AgentOut]


class AgentPatchOut(BaseModel):
    id: UUID
    name: str
    config: dict[str, Any]
    auto_improve_threshold: float | None
    auto_improve_rollback_delta: float


class VibeAgentOut(BaseModel):
    name: str
    template: str
    system_prompt: str
    tools: dict[str, bool]


class ExecuteOut(BaseModel):
    execution_id: UUID
    thread_id: UUID


class ConfidenceTrendItem(BaseModel):
    confidence: float
    created_at: datetime
    execution_id: UUID


class AgentStatsOut(BaseModel):
    agent_id: UUID
    total_runs: int
    avg_confidence: float
    grade_distribution: dict[int, int]
    confidence_trend: list[ConfidenceTrendItem]
    last_run_at: datetime | None
