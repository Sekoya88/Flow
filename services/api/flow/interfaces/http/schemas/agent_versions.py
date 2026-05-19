from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

# ── Inputs ────────────────────────────────────────────────────────────────────


class SnapshotCreateIn(BaseModel):
    version_label: str


# ── Outputs ───────────────────────────────────────────────────────────────────


class AgentVersionOut(BaseModel):
    id: UUID
    agent_id: UUID
    version_label: str
    config_snapshot: dict[str, Any]
    trigger: str
    status: str
    created_at: datetime


class AgentVersionListOut(BaseModel):
    versions: list[AgentVersionOut]


class VersionDiffOut(BaseModel):
    version_a: str
    version_b: str
    diff: dict[str, Any]


class VersionRestoreOut(BaseModel):
    ok: bool
    restored_to: str
