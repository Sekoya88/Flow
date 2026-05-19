from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_build_memory_store_pool_returns_async_connection_pool():
    """build_memory_store_pool returns an AsyncConnectionPool (not yet opened)."""
    from psycopg_pool import AsyncConnectionPool

    from flow.infrastructure.db.store import build_memory_store_pool
    pool = build_memory_store_pool("postgresql://flow:flow@localhost:55432/flow")
    assert pool is not None
    assert isinstance(pool, AsyncConnectionPool)
    # Pool is created with open=False, so it starts closed (opens on first use)
    assert pool.closed


def test_create_memory_store_wraps_pool():
    """create_memory_store returns an AsyncPostgresStore wrapping the pool."""
    from flow.infrastructure.db.store import create_memory_store
    mock_pool = MagicMock()
    with patch("langgraph.store.postgres.aio.AsyncPostgresStore") as MockStore:
        MockStore.return_value = MagicMock()
        store = create_memory_store(mock_pool)
        MockStore.assert_called_once_with(mock_pool)
        assert store is MockStore.return_value
