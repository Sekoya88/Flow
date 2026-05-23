from __future__ import annotations

import httpx

from ..auth import get_current_context
from ..config import settings


def register_agent_list_resource(mcp):  # type: ignore[no-untyped-def]

    @mcp.resource("flow://agents")
    async def agent_list_resource() -> str:
        """Active agents in the current workspace."""
        ctx = get_current_context()
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{settings.flow_api_url}/api/v1/agents",
                params={"workspace_id": ctx.get("workspace_id")},
                headers={"Authorization": f"Bearer {ctx.get('token', '')}"},
            )
            r.raise_for_status()
            agents = r.json()
        lines = [f"- [{a['name']}] id={a['id']}" for a in agents]
        return "\n".join(lines) if lines else "No agents found."
