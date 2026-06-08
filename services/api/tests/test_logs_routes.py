"""Tests for new /logs/training and /logs/research routes."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.list_workspaces_for_user = AsyncMock(return_value=[{"id": uuid4()}])
    return repo


@pytest.mark.asyncio
async def test_list_training_logs_returns_runs(mock_repo):
    from flow.interfaces.http.routes.logs import list_training_logs

    mock_repo._pool = MagicMock()
    mock_repo._pool.fetch = AsyncMock(
        return_value=[
            {
                "id": uuid4(),
                "skill_id": uuid4(),
                "skill_name": "my-skill",
                "status": "done",
                "best_score": 0.85,
                "epoch": 3,
                "error_message": None,
                "created_at": datetime.datetime.utcnow(),
                "completed_at": datetime.datetime.utcnow(),
                "duration_ms": 12000.0,
            }
        ]
    )
    result = await list_training_logs(user_id=uuid4(), repo=mock_repo, limit=10, skill_id=None)
    assert "runs" in result
    assert len(result["runs"]) == 1
    assert result["runs"][0]["skill_name"] == "my-skill"
    assert result["runs"][0]["epoch"] == 3


@pytest.mark.asyncio
async def test_list_research_logs_returns_runs(mock_repo):
    from flow.interfaces.http.routes.logs import list_research_logs

    mock_repo.list_digest_runs = AsyncMock(
        return_value=[
            {
                "id": uuid4(),
                "status": "done",
                "source": "arxiv",
                "paper_count": 5,
                "error": None,
                "started_at": datetime.datetime.utcnow(),
                "completed_at": datetime.datetime.utcnow(),
                "duration_ms": 45000.0,
            }
        ]
    )
    result = await list_research_logs(user_id=uuid4(), repo=mock_repo, limit=10)
    assert "runs" in result
    assert len(result["runs"]) == 1
    assert result["runs"][0]["source"] == "arxiv"
    assert result["runs"][0]["paper_count"] == 5
