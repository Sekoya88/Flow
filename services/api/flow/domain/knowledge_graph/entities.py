from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class NodeType(StrEnum):
    NOTE = "note"
    CONCEPT = "concept"
    TOPIC = "topic"
    QUERY = "query"


class EdgeType(StrEnum):
    LINKS_TO = "links_to"
    TAGGED_WITH = "tagged_with"
    MENTIONS = "mentions"
    SIMILAR_TO = "similar_to"
    BELONGS_TO = "belongs_to"
    REFERENCED_BY = "referenced_by"


class KGNode(BaseModel):
    id: UUID
    workspace_id: UUID
    label: str
    node_type: NodeType
    source_path: str | None = None
    content_hash: str | None = None
    summary: str | None = None
    embedding: list[float] | None = None
    metadata: dict[str, Any] = {}
    cluster_id: int | None = None
    pagerank: float = 0.0
    pos_x: float = 0.0
    pos_y: float = 0.0
    created_at: datetime
    updated_at: datetime


class KGEdge(BaseModel):
    id: UUID
    workspace_id: UUID
    source_id: UUID
    target_id: UUID
    edge_type: EdgeType
    weight: float = 1.0
    metadata: dict[str, Any] = {}
    created_at: datetime
