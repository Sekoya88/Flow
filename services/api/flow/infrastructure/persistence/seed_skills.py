"""Seed all skill templates to a target agent.

Usage:
    python -m flow.infrastructure.persistence.seed_skills --agent-id <uuid> [--db-url <url>]

Seeds all 19 templates from SKILL_TEMPLATES as active skills.
Skips skills that already exist (by name) for the agent.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from uuid import UUID

import asyncpg

from flow.infrastructure.persistence.skill_templates import SKILL_TEMPLATES


async def seed(agent_id: UUID, db_url: str) -> None:
    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
    try:
        workspace_row = await pool.fetchrow("SELECT workspace_id FROM agents WHERE id = $1", agent_id)
        if not workspace_row:
            print(f"Agent {agent_id} not found.", file=sys.stderr)
            sys.exit(1)
        workspace_id = workspace_row["workspace_id"]

        existing = {
            r["name"]
            for r in await pool.fetch(
                "SELECT name FROM agent_skills WHERE agent_id = $1 AND active = true",
                agent_id,
            )
        }

        created = skipped = 0
        for tmpl in SKILL_TEMPLATES:
            if tmpl["name"] in existing:
                print(f"  skip  {tmpl['name']}")
                skipped += 1
                continue
            await pool.execute(
                """
                INSERT INTO agent_skills
                    (agent_id, workspace_id, name, content_md, category, active, version)
                VALUES ($1, $2, $3, $4, $5, true, 1)
                ON CONFLICT DO NOTHING
                """,
                agent_id,
                workspace_id,
                tmpl["name"],
                tmpl["content_md"],
                tmpl["category"],
            )
            print(f"  create {tmpl['name']} [{tmpl['category']}]")
            created += 1

        print(f"\nDone: {created} created, {skipped} skipped.")
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed skill templates to an agent")
    parser.add_argument("--agent-id", required=True, help="Target agent UUID")
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL", "postgresql://localhost/flow"),
        help="PostgreSQL connection URL",
    )
    args = parser.parse_args()

    asyncio.run(seed(UUID(args.agent_id), args.db_url))


if __name__ == "__main__":
    main()
