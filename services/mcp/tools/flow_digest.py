from __future__ import annotations

from typing import Optional

import httpx
import structlog

from ..auth import get_current_context
from ..config import settings

logger = structlog.get_logger()


def register_flow_digest_tools(mcp):  # type: ignore[no-untyped-def]

    @mcp.tool()
    async def flow_digest_papers(
        status: Optional[str] = None,
        relevance_min: float = 0.0,
        limit: int = 20,
    ) -> list:
        """List research papers from the Flow daily digest (arXiv + HuggingFace).

        The digest runs daily at 8AM UTC, scoring papers by workspace interests.
        Returns [{id, title, abstract, tldr, relevance_score, status, categories, published_at}].
        status filter: 'unread' | 'read' | 'archived'
        relevance_min: float 0.0–1.0 — filter by AI relevance score (try 0.7 for high-signal)
        Papers with obsidian_path have been exported to your Obsidian vault.
        """
        ctx = get_current_context()
        logger.info("flow_digest_papers", status=status, relevance_min=relevance_min)
        params: dict = {"workspace_id": ctx["workspace_id"], "limit": limit}
        if status:
            params["status"] = status
        if relevance_min > 0.0:
            params["relevance_min"] = relevance_min
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                f"{settings.flow_api_url}/api/v1/digest/papers",
                params=params,
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            r.raise_for_status()
            data = r.json()
            papers = data.get("papers", data) if isinstance(data, dict) else data
            return papers[:limit]

    @mcp.tool()
    async def flow_trigger_digest() -> dict:
        """Trigger an immediate research digest run (arXiv + HuggingFace fetch + scoring).

        Normally runs automatically at 8AM UTC. Use this to get fresh papers now.
        Returns {status, message} — digest runs asynchronously via the ARQ worker.
        Papers appear in flow_digest_papers within ~2–5 minutes after triggering.
        Requires digest to be configured for the workspace (via /api/v1/digest/config).
        """
        ctx = get_current_context()
        logger.info("flow_trigger_digest", workspace=ctx.get("workspace_id"))
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{settings.flow_api_url}/api/v1/digest/run",
                json={"workspace_id": ctx["workspace_id"]},
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            r.raise_for_status()
            return r.json()

    @mcp.tool()
    async def flow_get_digest_config() -> dict:
        """Get the research digest configuration for the current workspace.

        Returns {enabled, schedule_hour, arxiv_categories, min_relevance_score,
                 user_interests, obsidian_mode, custom_sources}.
        arxiv_categories example: ['cs.AI', 'cs.LG', 'cs.CL', 'cs.CV']
        Edit via the Flow web UI at /settings or the API PUT /api/v1/digest/config.
        """
        ctx = get_current_context()
        logger.info("flow_get_digest_config", workspace=ctx.get("workspace_id"))
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{settings.flow_api_url}/api/v1/digest/config",
                params={"workspace_id": ctx["workspace_id"]},
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            if r.status_code == 404:
                return {"configured": False, "message": "Digest not configured for this workspace"}
            r.raise_for_status()
            return r.json()
