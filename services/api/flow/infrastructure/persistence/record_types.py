"""TypedDicts for asyncpg Record objects returned by FlowRepository.

asyncpg returns Record objects (not plain dicts). These TypedDicts document
the expected shape for type checkers without runtime overhead.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict
from uuid import UUID


class DigestRunRecord(TypedDict):
    """Shape of rows from the digest_runs table."""
    id: UUID
    workspace_id: UUID
    status: str            # "running" | "done" | "failed"
    source: str | None
    paper_count: int
    error: str | None
    started_at: datetime
    completed_at: datetime | None


class DigestPaperRecord(TypedDict):
    """Shape of rows from the digest_papers table."""
    id: UUID
    workspace_id: UUID
    title: str
    abstract: str | None
    source_url: str | None
    arxiv_id: str | None
    authors: list[str]
    categories: list[str]
    relevance_score: float
    tldr: str | None
    key_insights: list[str]
    summary_md: str | None
    obsidian_path: str | None
    status: str
    published_at: str | None
    digest_run_id: UUID | None


class TrainingRunRecord(TypedDict):
    """Shape of rows from skill_training_runs joined with skills."""
    id: UUID
    skill_id: UUID
    skill_name: str
    status: str            # "pending" | "running" | "done" | "failed"
    best_score: float | None
    epochs: list[Any]      # JSONB epoch results
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
