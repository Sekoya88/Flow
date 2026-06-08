from __future__ import annotations

import re
from importlib import resources

import asyncpg

from flow.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


def _split_sql(sql: str) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        if re.match(r"^\s*--", line):
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        out.append(tail)
    return out


async def apply_schema(pool: asyncpg.Pool) -> None:
    raw = resources.files("flow.infrastructure.db").joinpath("schema.sql").read_text(encoding="utf-8")
    statements = _split_sql(raw)
    async with pool.acquire() as conn:
        for stmt in statements:
            try:
                await conn.execute(stmt)
            except Exception as exc:
                logger.warning("schema.statement_failed", stmt=stmt[:80], error=str(exc)[:200])
                raise
    logger.info("schema.applied", statements=len(statements))
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE agents
            SET config = config || jsonb_build_object(
                'tools',
                '{"retrieve": true, "sandbox": true, "long_term_memory": true}'::jsonb
            )
            WHERE NOT (config ? 'tools')
            """
        )
    logger.info("schema.agent_tools_defaulted")
    async with pool.acquire() as conn:
        await conn.execute("ALTER TABLE knowledge_sources ADD COLUMN IF NOT EXISTS ingest_status TEXT NOT NULL DEFAULT 'indexed'")
        await conn.execute("ALTER TABLE knowledge_sources ADD COLUMN IF NOT EXISTS ingest_error TEXT")
        await conn.execute(
            """
            ALTER TABLE proposals ADD COLUMN IF NOT EXISTS execution_id UUID
            REFERENCES executions (id) ON DELETE SET NULL
            """
        )
    logger.info("schema.knowledge_ingest_and_proposal_exec_columns")
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS digest_runs (
                    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                    status       TEXT NOT NULL DEFAULT 'running',
                    source       TEXT,
                    paper_count  INT  NOT NULL DEFAULT 0,
                    error        TEXT,
                    started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMPTZ
                )
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS digest_runs_ws_idx ON digest_runs (workspace_id, started_at DESC)")
            await conn.execute("ALTER TABLE digest_papers ADD COLUMN IF NOT EXISTS digest_run_id UUID REFERENCES digest_runs(id) ON DELETE SET NULL")
            await conn.execute("CREATE INDEX IF NOT EXISTS digest_papers_run_idx ON digest_papers (digest_run_id)")
            await conn.execute("ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS obsidian_vault_path TEXT")
    logger.info("schema.digest_runs_and_obsidian_vault_path")
