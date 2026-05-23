from __future__ import annotations

import httpx

from ..auth import get_current_context
from ..config import settings


def register_flow_knowledge_tools(mcp):  # type: ignore[no-untyped-def]

    @mcp.tool()
    async def flow_ingest_knowledge(
        title: str,
        content: str,
        source_url: str = "",
        metadata: dict | None = None,
    ) -> dict:
        """Ingest a document into the Flow knowledge base (RAG + pgvector).
        Returns knowledge_id for referencing in Obsidian notes."""
        ctx = get_current_context()
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{settings.flow_api_url}/api/v1/knowledge",
                json={
                    "title": title,
                    "content": content,
                    "source_url": source_url,
                    "metadata": metadata or {},
                    "workspace_id": ctx["workspace_id"],
                },
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            r.raise_for_status()
            return r.json()

    @mcp.tool()
    async def flow_search_knowledge(query: str, limit: int = 5) -> list:
        """Semantic search in the Flow knowledge base."""
        ctx = get_current_context()
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{settings.flow_api_url}/api/v1/knowledge/search",
                json={
                    "query": query,
                    "limit": limit,
                    "workspace_id": ctx["workspace_id"],
                },
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            r.raise_for_status()
            return r.json()
