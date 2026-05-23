"""Seed best-practice memories for an agent.

Usage:
    python -m flow.infrastructure.persistence.seed_memory --agent-id <uuid> [--db-url <url>]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from uuid import UUID

import asyncpg

SEED_MEMORIES: list[str] = [
    "When asked to summarize, prefer bullet points over prose unless the user requests otherwise.",
    "Always cite sources when providing factual information retrieved from the web.",
    "For code snippets, always specify the programming language in the markdown fence.",
    "When multiple interpretations of a request exist, state your interpretation before answering.",
    "Prefer concise answers with examples over lengthy explanations without them.",
    "When the user asks 'why', provide the root reason, not just what happened.",
    "Never fabricate URLs, citations, or statistics — say you don't know instead.",
    "For technical tasks, confirm your understanding of the goal before executing multi-step plans.",
    "When debugging, provide the most likely root cause first, not a list of everything that could go wrong.",
    "Acknowledge when a question is outside your knowledge cutoff date and suggest where to find current info.",
]


async def seed(agent_id: UUID, db_url: str) -> None:
    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
    try:
        workspace_row = await pool.fetchrow("SELECT workspace_id FROM agents WHERE id = $1", agent_id)
        if not workspace_row:
            print(f"Agent {agent_id} not found.", file=sys.stderr)
            sys.exit(1)
        workspace_id = workspace_row["workspace_id"]

        for mem in SEED_MEMORIES:
            await pool.execute(
                """
                INSERT INTO agent_memories (agent_id, workspace_id, content)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
                """,
                agent_id,
                workspace_id,
                mem,
            )
            print(f"  wrote: {mem[:70]}…")

        print(f"\nDone: {len(SEED_MEMORIES)} memories seeded.")
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed best-practice memories to an agent")
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
