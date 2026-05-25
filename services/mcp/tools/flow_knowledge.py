from __future__ import annotations

import httpx
import structlog

from ..auth import get_current_context
from ..config import settings

logger = structlog.get_logger()


def register_flow_knowledge_tools(mcp):  # type: ignore[no-untyped-def]

    @mcp.tool()
    async def flow_ingest_knowledge(
        title: str,
        content: str,
        source_url: str = "",
        metadata: dict | None = None,
    ) -> dict:
        """Ingest a document into the Flow knowledge base (RAG + pgvector + Qdrant).

        Content is chunked, embedded, and dual-written to Postgres and Qdrant.
        Use for: articles, research notes, documentation, meeting summaries.
        Returns {id, status} — status may be 'processing' initially, then 'indexed'.
        After ingestion, content is searchable via flow_search_knowledge.
        """
        ctx = get_current_context()
        logger.info("flow_ingest_knowledge", title=title, source_url=source_url)
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
        """Semantic search in the Flow knowledge base (hybrid BM25 + dense embeddings).

        Uses Qdrant hybrid search (sparse BM25 + OpenAI dense) fused via RRF.
        Returns [{id, title, content_chunk, score, source_url, metadata}].
        Higher score = more relevant. Use limit=10 for broader results.
        Falls back to Tavily web search if local knowledge is insufficient.
        """
        ctx = get_current_context()
        logger.info("flow_search_knowledge", query=query, limit=limit)
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
