"""Tests for FlowRepository skill-training methods (Task 3).

All tests mock self._pool so no live database is required.
"""

import json
from unittest.mock import AsyncMock, MagicMock, call
from uuid import UUID, uuid4

import pytest

from flow.infrastructure.persistence.repo import FlowRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo() -> tuple[FlowRepository, MagicMock]:
    """Return a FlowRepository instance with a mocked asyncpg pool."""
    pool = MagicMock()
    pool.fetchrow = AsyncMock()
    pool.fetch = AsyncMock()
    pool.execute = AsyncMock()
    repo = FlowRepository.__new__(FlowRepository)
    repo._pool = pool  # type: ignore[attr-defined]
    return repo, pool


# ---------------------------------------------------------------------------
# create_training_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_training_run_returns_uuid():
    repo, pool = _make_repo()
    expected_id = uuid4()
    pool.fetchrow.return_value = {"id": expected_id}

    skill_id = uuid4()
    agent_id = uuid4()
    workspace_id = uuid4()

    result = await repo.create_training_run(
        skill_id=skill_id,
        agent_id=agent_id,
        workspace_id=workspace_id,
        edit_budget=10,
    )

    assert result == expected_id
    pool.fetchrow.assert_awaited_once()
    # Verify positional args passed to fetchrow
    args = pool.fetchrow.call_args[0]
    assert args[1] == skill_id
    assert args[2] == agent_id
    assert args[3] == workspace_id
    assert args[4] == 10


# ---------------------------------------------------------------------------
# update_training_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_training_run_builds_correct_set_clause():
    repo, pool = _make_repo()
    run_id = uuid4()

    await repo.update_training_run(
        run_id,
        status="running",
        epoch=2,
        edits_used=5,
        started_at=True,
    )

    pool.execute.assert_awaited_once()
    query: str = pool.execute.call_args[0][0]
    assert "status = $2" in query
    assert "epoch = $3" in query
    assert "edits_used = $4" in query
    assert "started_at = now()" in query
    assert "WHERE id = $1" in query

    # Values passed: run_id, "running", 2, 5
    args = pool.execute.call_args[0]
    assert args[1] == run_id
    assert args[2] == "running"
    assert args[3] == 2
    assert args[4] == 5


@pytest.mark.asyncio
async def test_update_training_run_no_fields_does_not_call_execute():
    repo, pool = _make_repo()
    run_id = uuid4()

    await repo.update_training_run(run_id)

    pool.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_training_run_completed_at():
    repo, pool = _make_repo()
    run_id = uuid4()

    await repo.update_training_run(run_id, accepted=True, completed_at=True)

    pool.execute.assert_awaited_once()
    query: str = pool.execute.call_args[0][0]
    assert "accepted = $2" in query
    assert "completed_at = now()" in query


# ---------------------------------------------------------------------------
# get_rejected_patches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_rejected_patches_parses_json_string_records():
    repo, pool = _make_repo()
    skill_id = uuid4()

    patch1 = json.dumps({"op": "replace", "target": "foo/bar", "value": 42})
    patch2 = json.dumps({"op": "add", "target": "baz/qux"})
    pool.fetch.return_value = [
        {"patch_json": patch1},
        {"patch_json": patch2},
    ]

    result = await repo.get_rejected_patches(skill_id)

    assert len(result) == 2
    assert result[0] == {"op": "replace", "target": "foo/bar"}
    assert result[1] == {"op": "add", "target": "baz/qux"}
    pool.fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_rejected_patches_handles_dict_records():
    """asyncpg may return JSONB as dict already (not string)."""
    repo, pool = _make_repo()
    skill_id = uuid4()

    pool.fetch.return_value = [
        {"patch_json": {"op": "remove", "target": "x/y"}},
    ]

    result = await repo.get_rejected_patches(skill_id)

    assert result == [{"op": "remove", "target": "x/y"}]


@pytest.mark.asyncio
async def test_get_rejected_patches_empty():
    repo, pool = _make_repo()
    pool.fetch.return_value = []

    result = await repo.get_rejected_patches(uuid4())

    assert result == []


# ---------------------------------------------------------------------------
# insert_training_epoch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_insert_training_epoch_calls_fetchrow_with_correct_args():
    repo, pool = _make_repo()
    expected_id = uuid4()
    pool.fetchrow.return_value = {"id": expected_id}

    run_id = uuid4()
    candidate_id = uuid4()

    result = await repo.insert_training_epoch(
        run_id=run_id,
        epoch=1,
        candidate_skill_id=candidate_id,
        eval_score=0.85,
        baseline_score=0.70,
        accepted=True,
        patch_count=3,
    )

    assert result == expected_id
    pool.fetchrow.assert_awaited_once()
    args = pool.fetchrow.call_args[0]
    # args[0] is the SQL query; args[1..] are positional params
    assert args[1] == run_id
    assert args[2] == 1
    assert args[3] == candidate_id
    assert args[4] == pytest.approx(0.85)
    assert args[5] == pytest.approx(0.70)
    assert args[6] is True
    assert args[7] == 3


@pytest.mark.asyncio
async def test_insert_training_epoch_none_candidate():
    repo, pool = _make_repo()
    pool.fetchrow.return_value = {"id": uuid4()}

    await repo.insert_training_epoch(
        run_id=uuid4(),
        epoch=0,
        candidate_skill_id=None,
        eval_score=0.5,
        baseline_score=0.5,
        accepted=False,
        patch_count=0,
    )

    args = pool.fetchrow.call_args[0]
    assert args[3] is None  # candidate_skill_id is None
