from __future__ import annotations

from typing import Optional

import httpx
import structlog

from ..auth import get_current_context
from ..config import settings

logger = structlog.get_logger()


def register_flow_agent_tools(mcp):  # type: ignore[no-untyped-def]

    @mcp.tool()
    async def flow_run_agent(agent_id: str, input: str) -> dict:
        """Run a Flow agent by ID with a text input.

        Use flow_list_agents first to discover available agent IDs.
        Returns {execution_id, status} — poll flow_get_execution until status='completed'.
        Agent answer is in flow_get_execution result's 'answer' field.
        Typical flow: list agents → pick agent_id → run → poll until done.
        """
        ctx = get_current_context()
        logger.info("flow_run_agent", agent_id=agent_id, workspace=ctx.get("workspace_id"))
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
        """Get the status and result of an agent execution.

        Status values: 'running' | 'completed' | 'failed'.
        When completed, 'answer' contains the agent's response text.
        Also returns 'thread_id' for multi-turn conversation continuity.
        """
        ctx = get_current_context()
        logger.info("flow_get_execution", execution_id=execution_id)
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{settings.flow_api_url}/api/v1/executions/{execution_id}",
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            r.raise_for_status()
            return r.json()

    @mcp.tool()
    async def flow_list_agents(category: Optional[str] = None) -> list:
        """List all agents in the current workspace.

        Returns [{id, name, template, config, created_at}] sorted by name.
        Use 'id' with flow_run_agent to execute an agent.
        Templates: 'deer_flow' (planner+worker+synthesizer), 'tool-agent', 'linear-3'.
        """
        ctx = get_current_context()
        logger.info("flow_list_agents", category=category, workspace=ctx.get("workspace_id"))
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
