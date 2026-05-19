from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID


class VersionStatus(StrEnum):
    CANDIDATE = "candidate"  # auto-triggered, awaiting proposal approval
    ACTIVE = "active"  # the live version for this agent
    ARCHIVED = "archived"  # superseded by a newer active version


class VersionTrigger(StrEnum):
    MANUAL = "manual"
    CONFIG_PATCH = "config_patch"
    SKILL_CREATED = "skill_created"
    EVAL_PASS = "eval_pass"


@dataclass
class ModelConfig:
    provider: str  # "openai" | "anthropic" | "ollama"
    model: str
    temperature: float
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentGenome:
    # Required (no defaults)
    agent_id: UUID
    version_label: str  # "v3" | "auto-skill-2026-05-08T03:00"
    template: str  # "deer_flow" | "linear-3" | "tool-agent"
    system_prompt: str  # first-class field
    llm_config: ModelConfig
    tools: dict[str, bool]  # {"retrieve": True, "sandbox": False, ...}
    status: VersionStatus
    trigger: VersionTrigger

    # Optional with factory defaults
    active_skill_ids: list[UUID] = field(default_factory=list)
    active_skill_names: list[str] = field(default_factory=list)  # denormalized for display

    # Optional with None defaults
    created_by: UUID | None = None
    created_at: datetime.datetime | None = None
    avg_score: float | None = None  # cached from last eval
    pass_rate: float | None = None
    proposal_id: UUID | None = None  # linked proposal (CANDIDATE only)
    id: UUID | None = None  # None until persisted

    def to_jsonb_dict(self) -> dict:
        """Convert to JSON-safe dict for asyncpg JSONB storage."""
        return {
            "agent_id": str(self.agent_id),
            "version_label": self.version_label,
            "template": self.template,
            "system_prompt": self.system_prompt,
            "llm_config": {
                **self.llm_config.extra,
                "provider": self.llm_config.provider,
                "model": self.llm_config.model,
                "temperature": self.llm_config.temperature,
            },
            "tools": self.tools,
            "active_skill_ids": [str(sid) for sid in self.active_skill_ids],
            "active_skill_names": self.active_skill_names,
            "status": self.status.value,
            "trigger": self.trigger.value,
            "created_by": str(self.created_by) if self.created_by else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "avg_score": self.avg_score,
            "pass_rate": self.pass_rate,
            "proposal_id": str(self.proposal_id) if self.proposal_id else None,
            "id": str(self.id) if self.id else None,
        }

    @classmethod
    def from_row(cls, row: dict) -> AgentGenome:
        """Reconstruct from a DB row dict (asyncpg Record or plain dict)."""
        llm_raw = row.get("llm_config") or row.get("model_config") or {}
        return cls(
            id=UUID(str(row["id"])) if row.get("id") else None,
            agent_id=UUID(str(row["agent_id"])),
            version_label=row["version_label"],
            template=row.get("template", "deer_flow"),
            system_prompt=row.get("system_prompt", ""),
            llm_config=ModelConfig(
                provider=llm_raw.get("provider", "openai"),
                model=llm_raw.get("model", "gpt-4o-mini"),
                temperature=float(llm_raw.get("temperature", 0.2)),
                extra={k: v for k, v in llm_raw.items() if k not in ("provider", "model", "temperature")},
            ),
            tools=row.get("tools", {}),
            active_skill_ids=[UUID(s) for s in (row.get("active_skill_ids") or [])],
            active_skill_names=row.get("active_skill_names") or [],
            status=VersionStatus(row.get("status", VersionStatus.ACTIVE)),
            trigger=VersionTrigger(row.get("trigger", VersionTrigger.MANUAL)),
            created_by=UUID(str(row["created_by"])) if row.get("created_by") else None,
            created_at=row.get("created_at"),
            avg_score=row.get("avg_score"),
            pass_rate=row.get("pass_rate"),
            proposal_id=UUID(str(row["proposal_id"])) if row.get("proposal_id") else None,
        )
