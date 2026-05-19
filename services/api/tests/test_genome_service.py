"""Tests for genome_service functions."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from flow.application.genome_service import get_active_genome


@pytest.mark.asyncio
async def test_get_active_genome_returns_active_version():
    """Should return the current active genome (not archived)."""
    agent_id = uuid4()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(
        return_value={
            "id": uuid4(),
            "agent_id": agent_id,
            "status": "active",
            "version_label": "v1",
            "template": "react-agent",
            "config_snapshot": '{"system_prompt": "hello", "tools": {}}',
            "avg_score": None,
            "pass_rate": None,
            "trigger": "manual",
            "created_by": None,
            "created_at": None,
            "proposal_id": None,
        }
    )
    result = await get_active_genome(pool, agent_id)
    assert result is not None
    assert result.status.value == "active"


@pytest.mark.asyncio
async def test_get_active_genome_returns_none_when_no_active():
    """Should return None when agent has no active genome."""
    agent_id = uuid4()
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    result = await get_active_genome(pool, agent_id)
    assert result is None
