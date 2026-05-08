"""Integration tests for Loop B: eval pass → genome snapshot → A/B test → proposal."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from flow.application.ab_runner import ABTestRunner, SIGNIFICANCE_THRESHOLD


@pytest.mark.asyncio
async def test_maybe_snapshot_skips_when_no_improvement():
    """should return None when new avg_score does not beat active version score"""
    from flow.application.genome_service import _maybe_snapshot_eval_pass

    active_genome = MagicMock()
    active_genome.avg_score = 0.85

    pool = AsyncMock()

    with patch("flow.application.genome_service.get_active_genome", return_value=active_genome):
        result = await _maybe_snapshot_eval_pass(
            pool=pool,
            agent_id=uuid4(),
            workspace_id=uuid4(),
            user_id=uuid4(),
            avg_score=0.80,  # lower than 0.85
            pass_rate=0.75,
        )

    assert result is None


@pytest.mark.asyncio
async def test_maybe_snapshot_creates_candidate_on_improvement():
    """should call snapshot_genome and return version UUID when score improves"""
    from flow.application.genome_service import _maybe_snapshot_eval_pass

    active_genome = MagicMock()
    active_genome.avg_score = 0.70

    pool = AsyncMock()
    new_version_id = uuid4()

    with patch("flow.application.genome_service.get_active_genome", return_value=active_genome), \
         patch("flow.application.genome_service.snapshot_genome", return_value=new_version_id) as mock_snap:
        result = await _maybe_snapshot_eval_pass(
            pool=pool,
            agent_id=uuid4(),
            workspace_id=uuid4(),
            user_id=uuid4(),
            avg_score=0.82,  # better than 0.70
            pass_rate=0.80,
        )

    assert result == new_version_id
    mock_snap.assert_called_once()
    # Should be created as CANDIDATE
    call_kwargs = mock_snap.call_args.kwargs
    from flow.domain.genome import VersionStatus, VersionTrigger
    assert call_kwargs["status"] == VersionStatus.CANDIDATE
    assert call_kwargs["trigger"] == VersionTrigger.EVAL_PASS


@pytest.mark.asyncio
async def test_maybe_snapshot_creates_candidate_when_no_active_genome():
    """should snapshot when there is no prior active version (first eval)"""
    from flow.application.genome_service import _maybe_snapshot_eval_pass

    pool = AsyncMock()
    new_version_id = uuid4()

    with patch("flow.application.genome_service.get_active_genome", return_value=None), \
         patch("flow.application.genome_service.snapshot_genome", return_value=new_version_id) as mock_snap:
        result = await _maybe_snapshot_eval_pass(
            pool=pool,
            agent_id=uuid4(),
            workspace_id=uuid4(),
            user_id=uuid4(),
            avg_score=0.75,
            pass_rate=0.80,
        )

    assert result == new_version_id
    mock_snap.assert_called_once()


def test_ab_summary_winner_is_version_b_when_delta_significant():
    """should set winner to version_b when delta >= threshold and version_b wins"""
    from flow.application.ab_runner import ABTestSummary, VersionScore

    version_a_id = uuid4()
    version_b_id = uuid4()
    golden_set_id = uuid4()
    test_id = uuid4()

    score_a = VersionScore(version_id=version_a_id, version_label="v1", avg_score=0.70, pass_rate=0.70, item_count=5)
    score_b = VersionScore(version_id=version_b_id, version_label="v2", avg_score=0.80, pass_rate=0.85, item_count=5)

    delta = score_b.avg_score - score_a.avg_score
    significant = abs(delta) >= SIGNIFICANCE_THRESHOLD
    winner = version_b_id if (significant and delta > 0) else (version_a_id if (significant and delta < 0) else None)

    summary = ABTestSummary(
        test_id=test_id,
        golden_set_id=golden_set_id,
        version_a=score_a,
        version_b=score_b,
        winner_version_id=winner,
        delta=delta,
        significant=significant,
    )

    assert summary.significant is True
    assert summary.winner_version_id == version_b_id
    assert summary.delta == pytest.approx(0.10)


def test_ab_summary_no_winner_when_delta_below_threshold():
    """should set winner to None when delta < SIGNIFICANCE_THRESHOLD"""
    from flow.application.ab_runner import ABTestSummary, VersionScore

    version_a_id = uuid4()
    version_b_id = uuid4()

    score_a = VersionScore(version_id=version_a_id, version_label="v1", avg_score=0.800, pass_rate=0.80, item_count=3)
    score_b = VersionScore(version_id=version_b_id, version_label="v2", avg_score=0.802, pass_rate=0.80, item_count=3)

    delta = score_b.avg_score - score_a.avg_score
    significant = abs(delta) >= SIGNIFICANCE_THRESHOLD

    assert significant is False

    summary = ABTestSummary(
        test_id=uuid4(),
        golden_set_id=uuid4(),
        version_a=score_a,
        version_b=score_b,
        winner_version_id=None,
        delta=delta,
        significant=significant,
    )

    assert summary.winner_version_id is None
    assert summary.significant is False


@pytest.mark.asyncio
async def test_ab_runner_run_returns_summary_with_correct_winner():
    """should return ABTestSummary identifying version_b as winner when scores differ"""
    from flow.application.ab_runner import ABTestRunner

    test_id = uuid4()
    golden_set_id = uuid4()
    agent_id = uuid4()
    version_a_id = uuid4()
    version_b_id = uuid4()

    pool = AsyncMock()
    # Version label lookup
    pool.fetch = AsyncMock(return_value=[
        {"id": version_a_id, "version_label": "v1"},
        {"id": version_b_id, "version_label": "v2"},
    ])
    pool.execute = AsyncMock()

    with patch.object(
        ABTestRunner,
        "_score_version",
        side_effect=[
            # version A scores
            MagicMock(
                version_id=version_a_id, version_label="v1",
                avg_score=0.60, pass_rate=0.60, item_count=5, per_item=[],
            ),
            # version B scores
            MagicMock(
                version_id=version_b_id, version_label="v2",
                avg_score=0.80, pass_rate=0.80, item_count=5, per_item=[],
            ),
        ],
    ):
        runner = ABTestRunner(pool=pool, client=MagicMock())
        summary = await runner.run(
            test_id=test_id,
            golden_set_id=golden_set_id,
            version_a_id=version_a_id,
            version_b_id=version_b_id,
            agent_id=agent_id,
        )

    assert summary.significant is True
    assert summary.winner_version_id == version_b_id
    assert summary.delta == pytest.approx(0.20)
    pool.execute.assert_called_once()  # UPDATE ab_tests SET status='completed'
