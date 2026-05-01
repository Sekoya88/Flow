"""Static metadata — schema overview + graph templates."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from flow.infrastructure.graph.spec import TEMPLATES, GraphSpec
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
        {
            "name": "rag_query_history",
            "columns": [
                "id",
                "execution_id",
                "workspace_id",
                "query_original",
                "routing_decision",
                "latency_ms (jsonb)",
                "explanation (jsonb)",
                "created_at",
            ],
        },
        {
            "name": "rag_citations",
            "columns": ["id", "query_history_id", "chunk_id", "excerpt", "relevance_score", "used_in_answer"],
        },
    ],
    "graph_checkpoints": "LangGraph AsyncPostgresSaver tables (managed by library, not in schema.sql).",
}


def _spec_to_flow_catalog(spec: GraphSpec) -> dict:
    """Topology for UI graph explorer (matches compile_graph wiring)."""
    step = 240
    base_y = 160
    nodes: list[dict] = []
    for i, nid in enumerate(spec.nodes):
        nodes.append(
            {
                "id": nid,
                "label": nid.replace("_", " ").title(),
                "x": 80 + i * step,
                "y": base_y,
            }
        )
    edges: list[dict] = [
        {"source": "__start__", "target": spec.entry, "kind": "fixed", "label": None},
    ]
    for src, dst in spec.edges:
        d = dst if dst != "END" else "__end__"
        edges.append({"source": src, "target": d, "kind": "fixed", "label": None})
    for ce in spec.conditional_edges:
        for branch_key, tgt in ce.mapping.items():
            t = tgt if tgt != "END" else "__end__"
            edges.append(
                {
                    "source": ce.source,
                    "target": t,
                    "kind": "conditional",
                    "label": f"{ce.condition}:{branch_key}",
                }
            )
    sink = {"id": "__end__", "label": "End", "x": 80 + len(spec.nodes) * step, "y": base_y}
    start = {"id": "__start__", "label": "Start", "x": 20, "y": base_y}
    return {
        "id": spec.template,
        "title": spec.template.replace("-", " ").replace("_", " ").title(),
        "nodes": [start, *nodes, sink],
        "edges": edges,
    }


# Mirrors agentic_rag/graph.py — layout optimized for React Flow–style canvas.
AGENTIC_RAG_CATALOG: dict = {
    "id": "agentic_rag",
    "title": "Agentic RAG (retrieval subgraph)",
    "description": (
        "Runs inside worker retrieval when FLOW_AGENTIC_RAG_ENABLED and Qdrant is configured; "
        "supervisor routes hybrid/dense retrieval, grading loop, optional web fallback."
    ),
    "nodes": [
        {"id": "__start__", "label": "Start", "x": 0, "y": 220},
        {"id": "supervisor", "label": "Supervisor", "x": 160, "y": 220},
        {"id": "retrieve", "label": "Retrieve", "x": 400, "y": 80},
        {"id": "web_search", "label": "Web search", "x": 400, "y": 220},
        {"id": "assemble_direct", "label": "Assemble direct", "x": 400, "y": 380},
        {"id": "grade_documents", "label": "Grade documents", "x": 640, "y": 80},
        {"id": "rewrite_question", "label": "Rewrite question", "x": 640, "y": 220},
        {"id": "web_fallback_flag", "label": "Web fallback", "x": 640, "y": 380},
        {"id": "assemble", "label": "Assemble", "x": 880, "y": 220},
        {"id": "finalize", "label": "Finalize", "x": 1120, "y": 220},
        {"id": "__end__", "label": "End", "x": 1320, "y": 220},
    ],
    "edges": [
        {"source": "__start__", "target": "supervisor", "kind": "fixed", "label": None},
        {"source": "supervisor", "target": "retrieve", "kind": "conditional", "label": "route→retrieve"},
        {"source": "supervisor", "target": "web_search", "kind": "conditional", "label": "route→web"},
        {"source": "supervisor", "target": "assemble_direct", "kind": "conditional", "label": "route→direct"},
        {"source": "retrieve", "target": "grade_documents", "kind": "fixed", "label": None},
        {"source": "grade_documents", "target": "assemble", "kind": "conditional", "label": "grade→assemble"},
        {"source": "grade_documents", "target": "rewrite_question", "kind": "conditional", "label": "grade→rewrite"},
        {"source": "grade_documents", "target": "web_fallback_flag", "kind": "conditional", "label": "grade→fallback"},
        {"source": "rewrite_question", "target": "supervisor", "kind": "fixed", "label": "loop"},
        {"source": "web_fallback_flag", "target": "web_search", "kind": "fixed", "label": None},
        {"source": "web_search", "target": "assemble", "kind": "fixed", "label": None},
        {"source": "assemble", "target": "finalize", "kind": "fixed", "label": None},
        {"source": "assemble_direct", "target": "finalize", "kind": "fixed", "label": None},
        {"source": "finalize", "target": "__end__", "kind": "fixed", "label": None},
    ],
}


def _deer_catalog_list() -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for spec in TEMPLATES.values():
        if spec.template in seen or spec.template == "deer_flow":
            continue
        seen.add(spec.template)
        out.append(_spec_to_flow_catalog(spec))
    return out


@router.get("/database")
async def database_overview(_user_id: Annotated[UUID, Depends(get_current_user_id)]) -> dict:
    return DATABASE_OVERVIEW


@router.get("/graph-catalog")
async def graph_catalog(_user_id: Annotated[UUID, Depends(get_current_user_id)]) -> dict:
    """Topology for agent pipeline + agentic RAG (for in-app graph explorer)."""
    return {
        "deer_flow_templates": _deer_catalog_list(),
        "agentic_rag": AGENTIC_RAG_CATALOG,
    }


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
