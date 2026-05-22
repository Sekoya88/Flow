from __future__ import annotations

import httpx

from ..auth import get_current_context
from ..config import settings


def register_flow_memory_tools(mcp):  # type: ignore[no-untyped-def]

    @mcp.tool()
    async def flow_memory_write(
        key: str,
        value: str,
        thread_id: str = "global",
    ) -> bool:
        """Write a fact to Flow persistent memory (AsyncPostgresStore).
        thread_id='global' for cross-thread workspace facts."""
        ctx = get_current_context()
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{settings.flow_api_url}/api/v1/memory",
                json={
                    "key": key,
                    "value": value,
                    "thread_id": thread_id,
                    "workspace_id": ctx["workspace_id"],
                },
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            return r.status_code == 200

    @mcp.tool()
    async def flow_memory_read(key: str, thread_id: str = "global") -> str:
        """Read a fact from Flow persistent memory."""
        ctx = get_current_context()
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{settings.flow_api_url}/api/v1/memory/{key}",
                params={"thread_id": thread_id, "workspace_id": ctx["workspace_id"]},
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            if r.status_code == 404:
                return ""
            r.raise_for_status()
            return r.json().get("value", "")
