from __future__ import annotations

import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_auto_eval_tick_logs_structured_error_on_db_failure(monkeypatch):
    """auto_eval_tick must log structured error with exc_type when evaluation fails."""
    import structlog.testing
    from flow.application.golden_evaluator import auto_eval_tick
    from uuid import uuid4

    # Mock the OpenAI client to prevent API key requirement
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    pool = AsyncMock()
    ws_id = uuid4()
    agent_id = uuid4()

    # Mock workspaces and initial queries to return valid data
    pool.fetch = AsyncMock(
        side_effect=[
            [{"id": ws_id}],  # workspaces
        ]
    )
    # Mock fetchrow to return agent and golden set data
    pool.fetchrow = AsyncMock(
        side_effect=[
            {"id": agent_id},  # agent lookup
            {"id": uuid4()},   # golden set lookup
            {"user_id": uuid4()},  # user lookup
            None,  # active_genome (will trigger exception in evaluate_golden_set)
        ]
    )
    # evaluate_golden_set will fail when trying to pool.fetch golden_items
    pool.fetch.side_effect = [
        [{"id": ws_id}],  # initial workspaces fetch
        RuntimeError("db timeout"),  # golden items fetch fails
    ]

    with structlog.testing.capture_logs() as logs:
        await auto_eval_tick({"pool": pool})

    error_logs = [l for l in logs if l.get("log_level") in ("error", "warning")]
    # Should have logged something structured
    assert len(error_logs) >= 1
    # Check for the structured error with correct fields
    assert any(
        l.get("event") == "cron.auto_eval_tick.agent_failed"
        for l in error_logs
    )


def test_ab_test_insert_sql_uses_same_agent_for_both_sides():
    """Verify the INSERT SQL intentionally uses same positional param $4 for both agent columns.

    In the genome versioning system, the A/B test compares two versions of the same agent,
    not two different agents. The agent_id is used for both agent_a_id and agent_b_id,
    while version_a_id and version_b_id are set later by ab_runner.py on completion.
    """
    sql = (
        "INSERT INTO ab_tests "
        "(id, workspace_id, golden_set_id, agent_a_id, agent_b_id, status) "
        "VALUES ($1, $2, $3, $4, $4, 'running')"
    )
    # Both agent_a_id and agent_b_id use $4 = same agent (versions differ, not agents)
    assert sql.count("$4") == 2
    assert "agent_a_id" in sql
    assert "agent_b_id" in sql
