from __future__ import annotations

import json

import httpx

from ..auth import get_current_context
from ..config import settings


def register_workspace_snapshot_resource(mcp):  # type: ignore[no-untyped-def]

    @mcp.resource("flow://workspace")
    async def workspace_snapshot_resource() -> str:
        """Full workspace context: agents, skills, knowledge, digest, KG stats.

        Returns JSON string — structured for machine parsing.
        Use this resource to get a complete picture of the workspace at session start.
        """
        ctx = get_current_context()
        headers = {"Authorization": f"Bearer {ctx.get('token', '')}"}
        workspace_id = ctx.get("workspace_id")

        results: dict = {"workspace_id": str(workspace_id)}

        async with httpx.AsyncClient(timeout=20.0) as client:
            # Agents
            try:
                r = await client.get(
                    f"{settings.flow_api_url}/api/v1/agents",
                    params={"workspace_id": workspace_id},
                    headers=headers,
                )
                if r.is_success:
                    agents = r.json()
                    results["agents"] = [
                        {"id": a.get("id"), "name": a.get("name"), "template": a.get("template")}
                        for a in agents
                    ]
                    results["agents_count"] = len(agents)
            except Exception:
                results["agents"] = []

            # Skills count
            try:
                r = await client.get(
                    f"{settings.flow_api_url}/api/v1/skills/catalog",
                    params={"workspace_id": workspace_id},
                    headers=headers,
                )
                if r.is_success:
                    results["skills_count"] = len(r.json())
            except Exception:
                results["skills_count"] = 0

            # Recent executions
            try:
                r = await client.get(
                    f"{settings.flow_api_url}/api/v1/executions",
                    headers=headers,
                )
                if r.is_success:
                    data = r.json()
                    execs = data.get("executions", data) if isinstance(data, dict) else data
                    results["recent_executions"] = [
                        {
                            "id": e.get("id"),
                            "agent_name": e.get("agent_name"),
                            "status": e.get("status"),
                            "created_at": e.get("created_at"),
                        }
                        for e in execs[:3]
                    ]
            except Exception:
                results["recent_executions"] = []

        return json.dumps(results, indent=2)
