from __future__ import annotations

from typing import Optional

import httpx

from ..auth import get_current_context
from ..config import settings


def register_flow_kg_tools(mcp):  # type: ignore[no-untyped-def]

    @mcp.tool()
    async def flow_kg_query(
        query: str,
        node_types: Optional[list[str]] = None,
    ) -> list:
        """Query the Flow Knowledge Graph.
        node_types can filter by: 'agent', 'skill', 'execution', 'knowledge', etc."""
        ctx = get_current_context()
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
        """Add a node to the Flow Knowledge Graph. Returns node_id."""
        ctx = get_current_context()
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
