"""Structured CV extraction shards — distinct Pydantic shapes per sub-agent facet group."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ToolingCvShard(BaseModel):
    """Structured output for tooling / stack extraction."""

    items: list[str] = Field(
        default_factory=list,
        max_length=40,
        description="Canonical names: languages, frameworks, clouds, data stores",
    )
    notes: str | None = Field(default=None, max_length=500)


class NarrativeCvShard(BaseModel):
    """Domain, goals, and communication-style hints — different shape from tooling."""

    domains: list[str] = Field(default_factory=list, max_length=12)
    goals: list[str] = Field(default_factory=list, max_length=12)
    style_hints: list[str] = Field(default_factory=list, max_length=12)


class VetoChannelCvShard(BaseModel):
    """Anti-patterns and preferred artifact shapes for code examples."""

    vetoes: list[str] = Field(default_factory=list, max_length=12)
    channels: list[str] = Field(default_factory=list, max_length=8)
