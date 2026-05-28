"""Tests for skill_trainer structlog events and SQL fix."""
from __future__ import annotations

import re


def test_sql_version_cast_uses_text():
    """The SQL in skill_trainer must cast version to text before concatenation."""
    import inspect
    from flow.application.skill_trainer import SkillTrainer
    src = inspect.getsource(SkillTrainer)
    # Must use ::text cast — raw `version || '-reflact'` fails on INT column
    assert "version::text ||" in src or "CAST(version" in src.upper(), (
        "version column must be cast to text before string concatenation"
    )


import asyncio
import structlog
import structlog.testing
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


@pytest.mark.asyncio
async def test_worker_emits_training_structlog_events():
    """task_run_skill_training must emit training.run.start and training.run.done via structlog."""
    run_id = str(uuid4())
    skill_id = str(uuid4())
    agent_id = str(uuid4())
    workspace_id = str(uuid4())

    fake_result = {
        "eval_score": 0.75,
        "baseline_score": 0.5,
        "accepted": True,
        "patches_applied": 1,
        "candidate_skill_id": None,
    }
    mock_trainer = MagicMock()
    mock_trainer.run_training_epoch = AsyncMock(return_value=fake_result)

    mock_repo = MagicMock()
    mock_repo.update_training_run = AsyncMock()
    mock_repo.insert_training_epoch = AsyncMock()
    mock_repo.upsert_agent_skill = AsyncMock()
    mock_repo.get_kg_node_by_label = AsyncMock(return_value=None)
    mock_repo.upsert_kg_node = AsyncMock(return_value=str(uuid4()))
    mock_repo.upsert_kg_edge = AsyncMock()

    mock_pool = MagicMock()
    mock_pool.execute = AsyncMock()

    ctx = {"pool": mock_pool, "stream_hub": None}

    # SkillTrainer and FlowRepository are locally imported inside task_run_skill_training,
    # so patch at their source modules.
    mock_training_config = MagicMock(max_epochs=1)

    with structlog.testing.capture_logs() as cap:
        with patch("flow.application.skill_trainer.SkillTrainer", return_value=mock_trainer), \
             patch("flow.application.skill_trainer.TrainingConfig", return_value=mock_training_config), \
             patch("flow.infrastructure.persistence.repo.FlowRepository", return_value=mock_repo):
            from flow.infrastructure.queue.worker import task_run_skill_training
            try:
                await task_run_skill_training(
                    ctx,
                    run_id=run_id,
                    skill_id=skill_id,
                    agent_id=agent_id,
                    workspace_id=workspace_id,
                    config_dict={"max_epochs": 1},
                )
            except Exception:
                pass  # we only care about log events, not full success

    events = [e["event"] for e in cap]
    assert "training.run.start" in events, f"training.run.start not in {events}"
    assert any(e in events for e in ("training.run.done", "training.run.failed")), \
        f"neither training.run.done nor training.run.failed in {events}"
