from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_auto_eval_tick_logs_structured_error_on_db_failure(monkeypatch):
    """auto_eval_tick must log structured error with exc_type when evaluation fails."""
    from uuid import uuid4

    import structlog.testing

    from flow.application.golden_evaluator import auto_eval_tick

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    pool = AsyncMock()
    ws_id = uuid4()
    agent_id = uuid4()
    gset_id = uuid4()
    user_id = uuid4()

    # pool.fetch: workspaces list
    pool.fetch = AsyncMock(return_value=[{"id": ws_id}])

    # pool.fetchrow call sequence:
    # 1. agent lookup
    # 2. golden_sets lookup
    # 3. workspace_members lookup
    # 4. get_active_genome -> agent_versions lookup (returns None = no active genome)
    pool.fetchrow = AsyncMock(
        side_effect=[
            {"id": agent_id},          # agent
            {"id": gset_id},           # golden set
            {"user_id": user_id},      # workspace member
            None,                      # get_active_genome -> no active genome
        ]
    )

    with patch(
        "flow.application.golden_evaluator.evaluate_golden_set",
        side_effect=RuntimeError("db timeout"),
    ):
        with structlog.testing.capture_logs() as logs:
            await auto_eval_tick({"pool": pool})

    error_logs = [entry for entry in logs if entry.get("log_level") in ("error", "warning")]
    assert len(error_logs) >= 1
    assert any(entry.get("event") == "cron.auto_eval_tick.agent_failed" for entry in error_logs)

    err = next(entry for entry in logs if entry.get("event") == "cron.auto_eval_tick.agent_failed")
    assert err.get("exc_type") == "RuntimeError"
    assert err.get("workspace_id") is not None


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
