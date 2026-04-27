"""Static metadata — schema overview + graph templates."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from flow.infrastructure.graph.spec import TEMPLATES
from flow.interfaces.http.deps import get_current_user_id

router = APIRouter(prefix="/api/v1/meta", tags=["meta"])

# Mirrors flow/infrastructure/db/schema.sql — keep in sync when migrations change.
DATABASE_OVERVIEW: dict = {
    "extensions": ["vector (pgvector)"],
    "tables": [
        {"name": "users", "columns": ["id", "email", "password_hash", "created_at"]},
        {"name": "workspaces", "columns": ["id", "name", "created_at"]},
        {
            "name": "workspace_members",
            "columns": ["workspace_id", "user_id", "role (admin|editor|viewer)"],
        },
        {
            "name": "agents",
            "columns": ["id", "workspace_id", "name", "template", "config (jsonb — tools.*)", "created_at"],
        },
        {
            "name": "executions",
            "columns": ["id", "agent_id", "workspace_id", "status", "error", "user_message", "timestamps"],
        },
        {"name": "execution_events", "columns": ["id", "execution_id", "kind", "payload (jsonb)", "created_at"]},
        {"name": "knowledge_sources", "columns": ["id", "workspace_id", "title", "body", "created_at"]},
        {"name": "knowledge_chunks", "columns": ["id", "source_id", "chunk_index", "content", "embedding vector(1536)"]},
        {"name": "user_preferences", "columns": ["user_id", "key", "value (jsonb)", "updated_at"]},
        {"name": "agent_memories", "columns": ["id", "workspace_id", "agent_id", "user_id", "content", "embedding", "created_at"]},
        {"name": "execution_feedback", "columns": ["id", "execution_id", "user_id", "score", "comment", "created_at"]},
        {"name": "proposals", "columns": ["id", "workspace_id", "user_id", "title", "body", "status", "created_at"]},
    ],
    "graph_checkpoints": "LangGraph AsyncPostgresSaver tables (managed by library, not in schema.sql).",
}


@router.get("/database")
async def database_overview(_user_id: Annotated[UUID, Depends(get_current_user_id)]) -> dict:
    return DATABASE_OVERVIEW


@router.get("/templates")
async def list_templates(_user_id: Annotated[UUID, Depends(get_current_user_id)]) -> dict:
    """List available graph templates with node topology."""
    return {
        "templates": [
            {
                "id": spec.template,
                "nodes": spec.nodes,
                "edges": [list(e) for e in spec.edges],
                "has_conditional": len(spec.conditional_edges) > 0,
            }
            for spec in TEMPLATES.values()
            if spec.template != "deer_flow"  # alias, don't show duplicate
        ]
    }
