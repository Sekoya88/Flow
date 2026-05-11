"""AsyncPostgresStore factory for cross-thread LangGraph memory."""
from __future__ import annotations

from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row


def build_memory_store_pool(database_url: str) -> AsyncConnectionPool:
    """Separate pool for AsyncPostgresStore (do not share with checkpoint pool)."""
    return AsyncConnectionPool(
        database_url,
        open=False,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        min_size=1,
        max_size=5,
    )


def create_memory_store(pool: AsyncConnectionPool):
    """Return an AsyncPostgresStore backed by pool. Call .setup() before first use."""
    from langgraph.store.postgres.aio import AsyncPostgresStore
    return AsyncPostgresStore(pool)
