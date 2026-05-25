from __future__ import annotations

from typing import Optional

import httpx
import structlog

from ..auth import get_current_context
from ..config import settings

logger = structlog.get_logger()


def register_flow_skill_tools(mcp):  # type: ignore[no-untyped-def]

    @mcp.tool()
    async def flow_create_skill(
        name: str,
        description: str,
        content: str,
        category: str = "General",
        tags: Optional[list[str]] = None,
    ) -> dict:
        """Create a reusable Flow skill (instruction set injected into agents).

        Content should follow Anthropic Skill Style: YAML frontmatter + markdown body.
        If content doesn't start with '---', frontmatter is auto-generated.
        Skills are versioned and scored by Flow's skill-bandit RL system.
        Returns {id, name, version, score} — use 'id' with flow_patch_skill to iterate.
        """
        ctx = get_current_context()
        logger.info("flow_create_skill", name=name, category=category)
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

        Flow uses an LLM to apply the patch while preserving skill structure.
        Example patch_prompt: 'Add a concrete Python example for use case 3'
        Example patch_prompt: 'Rewrite section 2 to be more concise'
        Returns the updated skill with incremented version number.
        """
        ctx = get_current_context()
        logger.info("flow_patch_skill", skill_id=skill_id)
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
        """List skills in the workspace.

        Returns [{id, name, description, category, score, version, tags}].
        'score' reflects RL-based performance (0.0–1.0) — higher = better performing.
        Filter by category (e.g. 'Research', 'Coding') or full-text search.
        """
        ctx = get_current_context()
        logger.info("flow_list_skills", category=category, search=search)
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
