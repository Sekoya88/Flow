from __future__ import annotations

import httpx
import structlog

from ..auth import get_current_context
from ..config import settings

logger = structlog.get_logger()


def register_flow_workspace_tools(mcp):  # type: ignore[no-untyped-def]

    @mcp.tool()
    async def flow_workspace_snapshot() -> dict:
        """Get a complete snapshot of the current Flow workspace.

        Returns a unified view of all workspace resources:
        {
          agents: [{id, name, template, status}],
          skills_count: int,
          knowledge_sources_count: int,
          kg_node_count: int,
          recent_executions: [{id, agent_name, status, created_at}],
          cron_jobs: [{name, description, next_run}]
        }
        Use this as the first call to orient yourself in a workspace before
        running agents, searching knowledge, or managing skills.
        """
        ctx = get_current_context()
        logger.info("flow_workspace_snapshot", workspace=ctx.get("workspace_id"))
        headers = {"Authorization": f"Bearer {ctx['token']}"}
        workspace_id = ctx["workspace_id"]

        async with httpx.AsyncClient(timeout=20.0) as client:
            agents_r, executions_r, schedules_r = await _gather(
                client.get(
                    f"{settings.flow_api_url}/api/v1/agents",
                    params={"workspace_id": workspace_id},
                    headers=headers,
                ),
                client.get(
                    f"{settings.flow_api_url}/api/v1/executions",
                    headers=headers,
                ),
                client.get(
                    f"{settings.flow_api_url}/api/v1/schedules",
                    params={"workspace_id": workspace_id},
                    headers=headers,
                ),
            )

        agents = agents_r.json() if agents_r.is_success else []
        executions_data = executions_r.json() if executions_r.is_success else {}
        schedules_data = schedules_r.json() if schedules_r.is_success else {}

        recent = executions_data.get("executions", [])[:5]
        system_jobs = schedules_data.get("system", [])

        return {
            "agents": [
                {"id": a.get("id"), "name": a.get("name"), "template": a.get("template")}
                for a in agents
            ],
            "agents_count": len(agents),
            "recent_executions": [
                {
                    "id": e.get("id"),
                    "agent_name": e.get("agent_name"),
                    "status": e.get("status"),
                    "user_message": (e.get("user_message") or "")[:80],
                    "created_at": e.get("created_at"),
                }
                for e in recent
            ],
            "system_cron_jobs": [
                {"name": j.get("name"), "description": j.get("description"), "next_run": j.get("next_run")}
                for j in system_jobs
            ],
        }

    @mcp.tool()
    async def flow_list_executions(limit: int = 10) -> list:
        """List recent agent executions across the workspace.

        Returns [{id, agent_name, status, user_message, answer, thread_id, created_at}].
        Status: 'running' | 'completed' | 'failed'.
        Use thread_id with flow_get_thread to retrieve a full conversation.
        Use flow_get_execution with an id to get full details of a single run.
        """
        ctx = get_current_context()
        logger.info("flow_list_executions", limit=limit)
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{settings.flow_api_url}/api/v1/executions",
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            r.raise_for_status()
            data = r.json()
            executions = data.get("executions", data) if isinstance(data, dict) else data
            return executions[:limit]

    @mcp.tool()
    async def flow_get_thread(thread_id: str) -> dict:
        """Get all executions in a conversation thread.

        Returns {thread_id, executions: [{id, user_message, answer, status, created_at}]}.
        Threads group multi-turn conversations with the same agent.
        thread_id comes from flow_list_executions or flow_get_execution response.
        """
        ctx = get_current_context()
        logger.info("flow_get_thread", thread_id=thread_id)
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{settings.flow_api_url}/api/v1/executions/threads/{thread_id}",
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            r.raise_for_status()
            return r.json()

    @mcp.tool()
    async def flow_list_schedules() -> dict:
        """List agent schedules and system cron jobs in the workspace.

        Returns {user_schedules: [{agent_id, cron_expr, delivery_type, enabled}],
                 system: [{name, description, cron_expr, next_run}]}.
        System jobs include: auto_eval (3AM), skill_decay (4AM), research_digest (8AM).
        User schedules are per-agent cron triggers with webhook or email delivery.
        """
        ctx = get_current_context()
        logger.info("flow_list_schedules", workspace=ctx.get("workspace_id"))
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{settings.flow_api_url}/api/v1/schedules",
                params={"workspace_id": ctx["workspace_id"]},
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            r.raise_for_status()
            return r.json()


async def _gather(*coros):  # type: ignore[no-untyped-def]
    """Run multiple httpx requests concurrently."""
    import asyncio
    return await asyncio.gather(*coros, return_exceptions=True)
