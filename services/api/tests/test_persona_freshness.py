"""Tests for persona_freshness.mark_stale_personas."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import uuid4

import pytest

from flow.application.persona_freshness import mark_stale_personas


def _make_pool(personas, newer_pref_result):
    """Return a minimal asyncpg.Pool mock."""
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=personas)
    pool.fetchrow = AsyncMock(return_value=newer_pref_result)
    pool.execute = AsyncMock(return_value=None)
    return pool


def _make_persona(*, stale: bool = False):
    row = MagicMock()
    row["id"] = uuid4()
    row["workspace_id"] = uuid4()
    row["user_id"] = uuid4()
    row["updated_at"] = datetime(2026, 1, 1, tzinfo=timezone.utc)
    row["derived_from"] = json.dumps({"stale_since": "2026-01-02T00:00:00+00:00"} if stale else {})
    return row


@pytest.mark.asyncio
async def test_no_personas_returns_zero():
    pool = _make_pool([], None)
    result = await mark_stale_personas(pool)
    assert result == 0


@pytest.mark.asyncio
async def test_persona_with_newer_pref_flagged():
    persona = _make_persona()
    pool = _make_pool([persona], MagicMock())  # fetchrow returns a row → newer pref exists
    result = await mark_stale_personas(pool)
    assert result == 1
    # execute should have been called with UPDATE containing stale_since
    pool.execute.assert_awaited_once()
    call_args = pool.execute.await_args
    patch_json = json.loads(call_args.args[1])
    assert "stale_since" in patch_json


@pytest.mark.asyncio
async def test_persona_without_newer_pref_not_flagged():
    persona = _make_persona()
    pool = _make_pool([persona], None)  # fetchrow returns None → no newer pref
    result = await mark_stale_personas(pool)
    assert result == 0
    pool.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_multiple_personas_only_stale_ones_updated():
    p1 = _make_persona()
    p2 = _make_persona()

    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[p1, p2])
    # First persona has newer pref, second does not
    pool.fetchrow = AsyncMock(side_effect=[MagicMock(), None])
    pool.execute = AsyncMock(return_value=None)

    result = await mark_stale_personas(pool)
    assert result == 1
    assert pool.execute.await_count == 1


@pytest.mark.asyncio
async def test_stale_since_is_valid_iso_timestamp():
    persona = _make_persona()
    pool = _make_pool([persona], MagicMock())
    await mark_stale_personas(pool)

    patch_arg = pool.execute.await_args.args[1]
    patch_data = json.loads(patch_arg)
    # Should parse without error
    dt = datetime.fromisoformat(patch_data["stale_since"])
    assert dt.tzinfo is not None
