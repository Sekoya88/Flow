"""Seed vendored curated skills + curated golden sets into a default 'Skill Library'
agent so a fresh workspace's Skill Hub is never empty. Idempotent."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import asyncpg

from flow.application.skill_parser import parse_skill_md
from flow.infrastructure.persistence.golden_seed import seed_curated_golden_sets
from flow.infrastructure.observability.logging import get_logger

log = get_logger("seed_collections")

VENDOR_DIR = Path(__file__).resolve().parent / "vendored_skills"
DEFAULT_AGENT_NAME = "Skill Library"


async def _ensure_library_agent(pool: asyncpg.Pool, workspace_id: uuid.UUID) -> uuid.UUID:
    row = await pool.fetchrow(
        "SELECT id FROM agents WHERE workspace_id=$1 AND name=$2", workspace_id, DEFAULT_AGENT_NAME
    )
    if row:
        return row["id"]
    agent_id = uuid.uuid4()
    await pool.execute(
        "INSERT INTO agents (id, workspace_id, name, template, config) VALUES ($1,$2,$3,$4,$5)",
        agent_id,
        workspace_id,
        DEFAULT_AGENT_NAME,
        "react-agent",
        json.dumps({"template": "react-agent", "system_prompt": "Curated skill library.", "tools": {}}),
    )
    log.info("library_agent.created", workspace_id=str(workspace_id))
    return agent_id


async def seed_collections(pool: asyncpg.Pool, workspace_id: uuid.UUID) -> dict:
    agent_id = await _ensure_library_agent(pool, workspace_id)
    existing = {
        r["name"]
        for r in await pool.fetch(
            "SELECT name FROM agent_skills WHERE agent_id=$1 AND active=true", agent_id
        )
    }
    created = 0
    if VENDOR_DIR.exists():
        for f in sorted(VENDOR_DIR.glob("*.md")):
            content_md = f.read_text(encoding="utf-8")
            parsed = parse_skill_md(content_md)
            name = parsed.name if parsed.name != "unnamed" else f.stem
            if name in existing:
                continue
            collection_cat = f.stem.split("__")[0]
            category = parsed.category if parsed.category != "General" else _category_for(collection_cat)
            await pool.execute(
                "INSERT INTO agent_skills (agent_id, workspace_id, name, content_md, category, active, version) "
                "VALUES ($1,$2,$3,$4,$5,true,1) ON CONFLICT DO NOTHING",
                agent_id,
                workspace_id,
                name,
                content_md,
                category,
            )
            existing.add(name)
            created += 1
    gsets = await seed_curated_golden_sets(pool, workspace_id)
    log.info("seed_collections.done", skills=created, golden_sets=gsets)
    return {"skills_created": created, "golden_sets_created": gsets}


def _category_for(collection_id: str) -> str:
    return {
        "mattpocock-skills": "Code",
        "scientific-agent-skills": "Research",
        "academic-research-skills": "Research",
        "ecc": "Code",
    }.get(collection_id, "General")


async def main() -> None:
    from flow.config import get_settings

    settings = get_settings()
    pool = await asyncpg.create_pool(settings.database_url)
    try:
        for ws in await pool.fetch("SELECT id FROM workspaces"):
            await seed_collections(pool, ws["id"])
    finally:
        await pool.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
