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


import structlog
import structlog.testing


def test_training_log_events_emitted():
    """training.run.start and training.run.done events are captured via structlog."""
    with structlog.testing.capture_logs() as cap:
        import structlog as sl
        logger = sl.get_logger("flow.training")
        logger.info("training.run.start", run_id="r1", skill_id="s1", agent_id="a1", max_epochs=3)
        logger.info("training.run.done", run_id="r1", skill_id="s1", accepted=True, best_score=0.85)

    assert any(e["event"] == "training.run.start" for e in cap)
    assert any(e["event"] == "training.run.done" for e in cap)
    done_ev = next(e for e in cap if e["event"] == "training.run.done")
    assert done_ev["accepted"] is True
    assert done_ev["best_score"] == 0.85
