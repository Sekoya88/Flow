from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ── Inputs ────────────────────────────────────────────────────────────────────

class KnowledgeCreateIn(BaseModel):
    workspace_id: UUID
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)


class KnowledgeCreateOut(BaseModel):
    id: UUID


class KnowledgeUploadOut(BaseModel):
    id: UUID
    title: str


class ChunkOut(BaseModel):
    id: UUID
    index: int
    content: str


class ChunkListOut(BaseModel):
    chunks: list[ChunkOut]


class KnowledgeSourceOut(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    chunk_count: int
    ingest_status: str = "indexed"
    ingest_error: str | None = None


class KnowledgeListOut(BaseModel):
    sources: list[KnowledgeSourceOut]
