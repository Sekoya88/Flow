"""Tests for skill_training_tick ARQ cron function."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from flow.infrastructure.queue.worker import skill_training_tick


@pytest.mark.asyncio
async def test_skill_training_tick_empty_db_does_not_enqueue():
    """should NOT call get_arq_pool when DB returns no eligible skills."""
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    ctx = {"pool": pool}

    # get_arq_pool is lazily imported inside the function from client module
    with patch("flow.infrastructure.queue.client.get_arq_pool") as mock_get_arq_pool:
        await skill_training_tick(ctx)
        mock_get_arq_pool.assert_not_called()


@pytest.mark.asyncio
async def test_skill_training_tick_one_skill_enqueues_job():
    """should call arq_pool.enqueue_job with job name 'run_skill_training' for one eligible skill."""
    skill_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    created_run_id = uuid.uuid4()

    row = {
        "skill_id": skill_id,
        "agent_id": agent_id,
        "workspace_id": workspace_id,
    }

    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[row])

    mock_arq_pool = AsyncMock()
    mock_arq_pool.enqueue_job = AsyncMock()

    ctx = {"pool": pool}

    class FakeRepo:
        def __init__(self, _pool):
            pass

        async def create_training_run(self, **kwargs):
            return created_run_id

    with patch("flow.infrastructure.queue.client.get_arq_pool", new=AsyncMock(return_value=mock_arq_pool)):
        with patch("flow.infrastructure.persistence.repo.FlowRepository", FakeRepo):
            await skill_training_tick(ctx)

    mock_arq_pool.enqueue_job.assert_called_once()
    call_args = mock_arq_pool.enqueue_job.call_args[0]
    assert call_args[0] == "run_skill_training", (
        f"Expected job name 'run_skill_training', got '{call_args[0]}'"
    )
    assert call_args[1] == str(created_run_id)
    assert call_args[2] == str(skill_id)
    assert call_args[3] == str(agent_id)
    assert call_args[4] == str(workspace_id)
