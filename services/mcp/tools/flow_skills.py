from __future__ import annotations

from typing import Optional

import httpx

from ..auth import get_current_context
from ..config import settings


def register_flow_skill_tools(mcp):  # type: ignore[no-untyped-def]

    @mcp.tool()
    async def flow_create_skill(
        name: str,
        description: str,
        content: str,
        category: str = "General",
        tags: Optional[list[str]] = None,
    ) -> dict:
        """Create a Flow skill. Content MUST follow Anthropic Skill Style:
        YAML front matter + XML-tagged sections + Markdown body."""
        ctx = get_current_context()
        if not content.startswith("---"):
            tag_list = tags or []
            content = (
                f"---\nname: {name}\ndescription: {description}\n"
                f"category: {category}\ntags: {tag_list}\nversion: 1\n---\n\n{content}"
            )
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{settings.flow_api_url}/api/v1/skills",
                json={
                    "name": name,
                    "description": description,
                    "content_md": content,
                    "category": category,
                    "workspace_id": ctx["workspace_id"],
                },
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            r.raise_for_status()
            return r.json()

    @mcp.tool()
    async def flow_patch_skill(skill_id: str, patch_prompt: str) -> dict:
        """Modify an existing skill via a natural language prompt (vibe-edit).
        Example: 'Add a Python example for use case 3'"""
        ctx = get_current_context()
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{settings.flow_api_url}/api/v1/skills/{skill_id}/vibe-modify",
                json={"prompt": patch_prompt, "workspace_id": ctx["workspace_id"]},
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            r.raise_for_status()
            return r.json()

    @mcp.tool()
    async def flow_list_skills(
        category: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list:
        """List skills in the workspace. Filterable by category or text search."""
        ctx = get_current_context()
        params: dict = {"workspace_id": ctx["workspace_id"]}
        if category:
            params["category"] = category
        if search:
            params["q"] = search
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{settings.flow_api_url}/api/v1/skills/catalog",
                params=params,
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            r.raise_for_status()
            return r.json()
