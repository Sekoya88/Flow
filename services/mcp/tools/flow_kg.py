from __future__ import annotations

from typing import Optional

import httpx
import structlog

from ..auth import get_current_context
from ..config import settings

logger = structlog.get_logger()


def register_flow_kg_tools(mcp):  # type: ignore[no-untyped-def]

    @mcp.tool()
    async def flow_kg_query(
        query: str,
        node_types: Optional[list[str]] = None,
    ) -> list:
        """Query the Flow Knowledge Graph with a natural language or structured query.

        The KG stores relationships between agents, skills, papers, and concepts.
        node_types filter: ['agent', 'skill', 'paper', 'concept', 'execution']
        Returns [{id, label, type, properties, score}] ranked by semantic relevance.
        Example: query='agents that use RAG retrieval', node_types=['agent']
        Example: query='recent transformer architecture papers'
        """
        ctx = get_current_context()
        logger.info("flow_kg_query", query=query, node_types=node_types)
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{settings.flow_api_url}/api/v1/kg/query",
                json={
                    "query": query,
                    "node_types": node_types,
                    "workspace_id": ctx["workspace_id"],
                },
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            r.raise_for_status()
            return r.json()

    @mcp.tool()
    async def flow_kg_add_node(
        label: str,
        node_type: str,
        properties: dict,
    ) -> str:
        """Add a node to the Flow Knowledge Graph. Returns node_id.

        node_type values: 'concept', 'paper', 'agent', 'skill', 'tool'
        properties is a free-form dict — include 'description', 'source_url', 'tags', etc.
        Nodes are embedded (OpenAI text-embedding-3-small) for semantic search via flow_kg_query.
        Example: label='Agentic RAG', node_type='concept', properties={'description': '...', 'tags': ['RAG']}
        """
        ctx = get_current_context()
        logger.info("flow_kg_add_node", label=label, node_type=node_type)
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{settings.flow_api_url}/api/v1/kg/nodes",
                json={
                    "label": label,
                    "type": node_type,
                    "properties": properties,
                    "workspace_id": ctx["workspace_id"],
                },
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            r.raise_for_status()
            return r.json()["id"]
