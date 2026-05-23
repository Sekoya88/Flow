from __future__ import annotations

import httpx

from ..auth import get_current_context
from ..config import settings


def register_skill_catalog_resource(mcp):  # type: ignore[no-untyped-def]

    @mcp.resource("flow://skills")
    async def skill_catalog_resource() -> str:
        """Full skill catalog for the current workspace."""
        ctx = get_current_context()
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{settings.flow_api_url}/api/v1/skills/catalog",
                params={"workspace_id": ctx.get("workspace_id")},
                headers={"Authorization": f"Bearer {ctx.get('token', '')}"},
            )
            r.raise_for_status()
            skills = r.json()
        lines = [
            f"- [{s['name']}] category={s.get('category', 'General')} score={s.get('score', 0)}"
            for s in skills
        ]
        return "\n".join(lines) if lines else "No skills found."
