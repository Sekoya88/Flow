from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class KGNodeOut(BaseModel):
    id: str
    label: str
    node_type: str
    summary: str | None
    source_path: str | None
    cluster_id: int | None
    pagerank: float
    pos_x: float
    pos_y: float
    metadata: dict[str, Any]


class KGEdgeOut(BaseModel):
    id: str
    source_id: str
    target_id: str
    edge_type: str
    weight: float


class KGGraphOut(BaseModel):
    nodes: list[KGNodeOut]
    edges: list[KGEdgeOut]
    cluster_count: int


class KGNodeDetailOut(BaseModel):
    node: KGNodeOut
    neighbors: list[KGNodeOut]
    edges: list[KGEdgeOut]


class KGIngestObsidianIn(BaseModel):
    workspace_id: UUID
    base_url: str
    api_key: str
    vault_path: str = "/"


class KGSyncIn(BaseModel):
    workspace_id: UUID
    vault_path: str


class KGQueryIn(BaseModel):
    workspace_id: UUID
    question: str
    stream: bool = True
