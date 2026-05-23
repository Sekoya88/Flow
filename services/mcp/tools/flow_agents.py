from __future__ import annotations

from typing import Optional

import httpx

from ..auth import get_current_context
from ..config import settings


def register_flow_agent_tools(mcp):  # type: ignore[no-untyped-def]

    @mcp.tool()
    async def flow_run_agent(agent_id: str, input: str) -> dict:
        """Run a Flow agent by ID with a text input.
        Returns execution_id to track progress via flow_get_execution."""
        ctx = get_current_context()
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{settings.flow_api_url}/api/v1/agents/{agent_id}/run",
                json={"input": input, "workspace_id": ctx["workspace_id"]},
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            r.raise_for_status()
            return r.json()

    @mcp.tool()
    async def flow_get_execution(execution_id: str) -> dict:
        """Get the status and result of an agent execution."""
        ctx = get_current_context()
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{settings.flow_api_url}/api/v1/executions/{execution_id}",
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            r.raise_for_status()
            return r.json()

    @mcp.tool()
    async def flow_list_agents(category: Optional[str] = None) -> list:
        """List all agents in the current workspace. Optionally filter by category."""
        ctx = get_current_context()
        params: dict = {"workspace_id": ctx["workspace_id"]}
        if category:
            params["category"] = category
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{settings.flow_api_url}/api/v1/agents",
                params=params,
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            r.raise_for_status()
            return r.json()
