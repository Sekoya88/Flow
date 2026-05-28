"""Unit tests for FlowRepository digest_run methods (mock asyncpg pool)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

WS_ID = uuid4()
RUN_ID = uuid4()


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    pool.fetchval = AsyncMock()
    pool.fetch = AsyncMock()
    pool.execute = AsyncMock()
    pool.fetchrow = AsyncMock()
    return pool


@pytest.fixture
def repo(mock_pool):
    from flow.infrastructure.persistence.repo import FlowRepository
    return FlowRepository(mock_pool)


@pytest.mark.asyncio
async def test_create_digest_run_returns_uuid(repo, mock_pool):
    mock_pool.fetchval.return_value = RUN_ID
    result = await repo.create_digest_run(WS_ID, source="arxiv")
    assert result == RUN_ID
    mock_pool.fetchval.assert_awaited_once()
    call_sql = mock_pool.fetchval.call_args[0][0]
    assert "INSERT INTO digest_runs" in call_sql


@pytest.mark.asyncio
async def test_update_digest_run_calls_execute(repo, mock_pool):
    await repo.update_digest_run(RUN_ID, status="done", paper_count=5)
    mock_pool.execute.assert_awaited_once()
    call_sql = mock_pool.execute.call_args[0][0]
    assert "digest_runs" in call_sql
    assert "status" in call_sql


@pytest.mark.asyncio
async def test_update_digest_run_raises_on_no_fields(repo, mock_pool):
    with pytest.raises(ValueError, match="no fields to update"):
        await repo.update_digest_run(RUN_ID)


@pytest.mark.asyncio
async def test_list_digest_runs_returns_records(repo, mock_pool):
    mock_pool.fetch.return_value = [{"id": RUN_ID, "status": "done"}]
    rows = await repo.list_digest_runs(WS_ID, limit=10)
    assert len(rows) == 1
    mock_pool.fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_digest_run_papers_returns_records(repo, mock_pool):
    mock_pool.fetch.return_value = [{"id": uuid4(), "title": "Test Paper"}]
    rows = await repo.get_digest_run_papers(RUN_ID)
    assert len(rows) == 1
    call_sql = mock_pool.fetch.call_args[0][0]
    assert "digest_run_id" in call_sql


@pytest.mark.asyncio
async def test_get_workspace_vault_path_returns_none_when_unset(repo, mock_pool):
    mock_pool.fetchval.return_value = None
    result = await repo.get_workspace_vault_path(WS_ID)
    assert result is None


@pytest.mark.asyncio
async def test_set_workspace_vault_path_calls_execute(repo, mock_pool):
    await repo.set_workspace_vault_path(WS_ID, "/Users/nick/Obsidian/Flow")
    mock_pool.execute.assert_awaited_once()
    call_sql = mock_pool.execute.call_args[0][0]
    assert "obsidian_vault_path" in call_sql
