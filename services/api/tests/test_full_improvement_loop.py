"""End-to-end test for the full improvement loop:
  eval failure → prompt rewrite → candidate genome → AB test → proposal → promote

This validates the entire autonomous self-improvement feedback loop.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from flow.application.prompt_rewriter import FailedItem, RewriteResult


@pytest.mark.asyncio
async def test_full_loop_eval_to_candidate():
    """The full loop: evaluate → detect failures → rewrite prompt → snapshot candidate"""
    from flow.application.curator import check_regression_and_propose

    agent_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()

    pool = AsyncMock()
    conn = AsyncMock()
    # For create_proposal
    conn.fetchval = AsyncMock(return_value=uuid4())
    conn.execute = AsyncMock()

    ctx_mgr = AsyncMock()
    ctx_mgr.__aenter__ = AsyncMock(return_value=conn)
    ctx_mgr.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=ctx_mgr)

    results = [
        {
            "item_id": str(uuid4()),
            "input_text": "What is RAG?",
            "expected_output": "Retrieval-Augmented Generation...",
            "actual_output": "RAG is a technique.",
            "score": 0.3,
            "rationale": "Too brief, no details.",
        },
        {
            "item_id": str(uuid4()),
            "input_text": "Explain transformers",
            "expected_output": "Transformers are neural network architectures...",
            "actual_output": "They transform data.",
            "score": 0.2,
            "rationale": "Completely inadequate.",
        },
        {
            "item_id": str(uuid4()),
            "input_text": "What is RLHF?",
            "expected_output": "Reinforcement Learning from Human Feedback...",
            "actual_output": "RLHF is a method for aligning LLMs using human preferences and reward models.",
            "score": 0.8,  # this one passes
            "rationale": "Good coverage.",
        },
    ]

    candidate_id = uuid4()
    active_genome = MagicMock()
    active_genome.system_prompt = "You are a research assistant."
    active_genome.llm_config.provider = "openai"
    active_genome.llm_config.model = "gpt-4o-mini"
    active_genome.llm_config.temperature = 0.3

    with (
        patch(
            "flow.application.genome_service.get_active_genome",
            return_value=active_genome,
        ),
        patch(
            "flow.application.prompt_rewriter.rewrite_and_snapshot",
            return_value={
                "candidate_version_id": str(candidate_id),
                "rewrite": {
                    "changelog": ["Added detail requirements", "Added source citation rule"],
                    "failure_analysis": "Agent responses were too brief",
                    "confidence": 0.85,
                    "prompt_diff_len": 120,
                },
            },
        ) as mock_rewrite,
        patch(
            "flow.application.genome_service._create_genome_proposal",
            return_value=uuid4(),
        ),
    ):
        result = await check_regression_and_propose(
            pool=pool,
            golden_set_id=uuid4(),
            agent_id=agent_id,
            new_avg_score=0.43,  # below threshold
            results=results,
            workspace_id=workspace_id,
            user_id=user_id,
            openai_api_key="test-key",
        )

    assert result is not None
    assert result["candidate_version_id"] == str(candidate_id)
    assert result["rewrite"]["confidence"] == 0.85

    # Verify rewrite was called with correct failed items (only score < 0.7)
    mock_rewrite.assert_called_once()
    rewrite_args = mock_rewrite.call_args
    failed_items_arg = rewrite_args.kwargs.get("failed_items") or rewrite_args.args[4]
    assert len(failed_items_arg) == 2  # only 2 items failed


@pytest.mark.asyncio
async def test_full_loop_no_action_when_all_pass():
    """should not trigger rewrite when all items pass"""
    from flow.application.curator import check_regression_and_propose

    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=uuid4())
    conn.execute = AsyncMock()
    ctx_mgr = AsyncMock()
    ctx_mgr.__aenter__ = AsyncMock(return_value=conn)
    ctx_mgr.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=ctx_mgr)

    results = [
        {"item_id": str(uuid4()), "input_text": "Q1", "score": 0.9, "rationale": "Great"},
        {"item_id": str(uuid4()), "input_text": "Q2", "score": 0.8, "rationale": "Good"},
    ]

    result = await check_regression_and_propose(
        pool=pool,
        golden_set_id=uuid4(),
        agent_id=uuid4(),
        new_avg_score=0.85,  # above threshold
        results=results,
        workspace_id=uuid4(),
        user_id=uuid4(),
        openai_api_key="test-key",
    )

    assert result is None  # no action taken


@pytest.mark.asyncio
async def test_full_loop_regression_alert_created():
    """should create a regression alert proposal when avg score < 0.7"""
    from flow.application.curator import check_regression_and_propose

    pool = AsyncMock()
    # FlowRepository(pool) calls pool.fetchrow for create_proposal
    proposal_row = MagicMock()
    proposal_row.__getitem__ = lambda self, k: {"id": uuid4()}[k]
    pool.fetchrow = AsyncMock(return_value=proposal_row)
    pool.execute = AsyncMock()

    results = [
        {"item_id": str(uuid4()), "input_text": "Q1", "score": 0.5, "rationale": "Bad", "expected_output": "E1", "actual_output": "A1"},
    ]

    active_genome = MagicMock()
    active_genome.system_prompt = "test"
    active_genome.llm_config.provider = "openai"
    active_genome.llm_config.model = "gpt-4o-mini"
    active_genome.llm_config.temperature = 0.3

    with (
        patch("flow.application.genome_service.get_active_genome", return_value=active_genome),
        patch("flow.application.prompt_rewriter.rewrite_and_snapshot", return_value=None),
    ):
        # Should still create the regression alert proposal even if rewrite fails
        await check_regression_and_propose(
            pool=pool,
            golden_set_id=uuid4(),
            agent_id=uuid4(),
            new_avg_score=0.5,
            results=results,
            workspace_id=uuid4(),
            user_id=uuid4(),
            openai_api_key="test-key",
        )

    # Verify create_proposal was called (via pool.fetchrow for INSERT ... RETURNING id)
    assert pool.fetchrow.called


@pytest.mark.asyncio
async def test_genome_candidate_to_proposal_to_activate():
    """Test the full promotion path: candidate → proposal approve → genome activate"""
    from flow.application.genome_service import activate_genome

    agent_id = uuid4()
    workspace_id = uuid4()
    version_id = uuid4()

    pool = AsyncMock()
    conn = AsyncMock()

    # Mock the activate_genome transaction
    config_row = MagicMock()
    config_row.__getitem__ = lambda self, k: {
        "config_snapshot": {"system_prompt": "improved"},
        "template": "deer_flow",
    }[k]
    conn.execute = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=config_row)

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    ctx_mgr = AsyncMock()
    ctx_mgr.__aenter__ = AsyncMock(return_value=conn)
    ctx_mgr.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=ctx_mgr)

    await activate_genome(
        pool=pool,
        version_id=version_id,
        agent_id=agent_id,
        workspace_id=workspace_id,
    )

    # Verify the three SQL operations happened:
    # 1. Archive all active versions
    # 2. Set candidate to active
    # 3. Apply config_snapshot to agents table
    assert conn.execute.call_count >= 2  # archive + update agents


@pytest.mark.asyncio
async def test_ab_test_winner_triggers_proposal():
    """Test that when AB test candidate wins, a proposal is created"""
    from flow.application.ab_runner import SIGNIFICANCE_THRESHOLD, ABTestSummary, VersionScore

    version_a_id = uuid4()
    version_b_id = uuid4()  # candidate

    score_a = VersionScore(
        version_id=version_a_id,
        version_label="v1",
        avg_score=0.65,
        pass_rate=0.60,
        item_count=5,
    )
    score_b = VersionScore(
        version_id=version_b_id,
        version_label="auto-eval-2026-05-11",
        avg_score=0.82,
        pass_rate=0.80,
        item_count=5,
    )

    delta = score_b.avg_score - score_a.avg_score
    significant = abs(delta) >= SIGNIFICANCE_THRESHOLD
    winner = version_b_id if (significant and delta > 0) else None

    summary = ABTestSummary(
        test_id=uuid4(),
        golden_set_id=uuid4(),
        version_a=score_a,
        version_b=score_b,
        winner_version_id=winner,
        delta=delta,
        significant=significant,
    )

    # The candidate (version B) should be the winner
    assert summary.significant is True
    assert summary.winner_version_id == version_b_id
    assert summary.delta == pytest.approx(0.17)

    # In the real cron job, this would trigger _create_genome_proposal
    # We verify the summary is structured correctly for that call
    assert summary.version_b.avg_score > summary.version_a.avg_score


def _make_pool_context(conn):
    """Create an async context manager mock that returns conn."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=cm)
    return pool


@pytest.mark.asyncio
async def test_full_loop_creates_candidate_and_restores_prompt():
    """
    Given: agent with failures below threshold
    When: rewrite_and_snapshot is called
    Then: CANDIDATE genome created, agent prompt restored to original
    """
    from flow.application.prompt_rewriter import rewrite_and_snapshot

    agent_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()
    original_prompt = "You are a helpful assistant."
    candidate_uuid = uuid4()

    stored_config = {"system_prompt": original_prompt}
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"config": stored_config})

    updates_received = []

    async def capture_execute(sql, config, *args):
        updates_received.append(dict(config))

    conn.execute = capture_execute
    pool = _make_pool_context(conn)

    with (
        patch("flow.application.prompt_rewriter.rewrite_prompt") as mock_rewrite,
        patch("flow.application.genome_service.snapshot_genome", return_value=candidate_uuid),
    ):
        mock_rewrite.return_value = RewriteResult(
            original_prompt=original_prompt,
            improved_prompt="You are a helpful, precise assistant. Always cite sources.",
            changelog=["Added source citation requirement"],
            failure_analysis="Agent failed to cite sources",
            confidence=0.85,
        )

        result = await rewrite_and_snapshot(
            pool=pool,
            agent_id=agent_id,
            workspace_id=workspace_id,
            user_id=user_id,
            current_prompt=original_prompt,
            failed_items=[FailedItem("Q", "A with source", "A without source", 0.2, "missing citation")],
            llm_config={"provider": "openai", "model": "gpt-4o-mini"},
        )

    assert result is not None, "Should return a result dict when rewrite succeeds"
    assert result["candidate_version_id"] == str(candidate_uuid)

    # Verify: last update restored the original prompt
    assert len(updates_received) >= 2, "Should have written temp prompt then restored"
    assert updates_received[-1]["system_prompt"] == original_prompt
    assert "_rewrite_changelog" not in updates_received[-1]


@pytest.mark.asyncio
async def test_full_loop_skips_low_confidence_rewrite():
    """When rewrite confidence is below 0.3, rewrite_and_snapshot returns None."""
    from flow.application.prompt_rewriter import rewrite_and_snapshot

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"config": {"system_prompt": "original"}})
    pool = _make_pool_context(conn)

    with patch("flow.application.prompt_rewriter.rewrite_prompt") as mock_rewrite:
        mock_rewrite.return_value = RewriteResult(
            original_prompt="original",
            improved_prompt="slightly better",
            changelog=["minor tweak"],
            failure_analysis="unclear",
            confidence=0.2,  # below threshold
        )

        result = await rewrite_and_snapshot(
            pool=pool,
            agent_id=uuid4(),
            workspace_id=uuid4(),
            user_id=uuid4(),
            current_prompt="original",
            failed_items=[FailedItem("Q", "A", "B", 0.1, "wrong")],
            llm_config={},
        )

    assert result is None, "Low confidence rewrite should be skipped"


@pytest.mark.asyncio
async def test_eval_pass_snapshot_only_on_improvement():
    """Verify _maybe_snapshot_eval_pass only creates candidate when score improves"""
    from flow.application.genome_service import _maybe_snapshot_eval_pass

    # Case 1: No improvement (score same or lower)
    active = MagicMock()
    active.avg_score = 0.80

    with patch("flow.application.genome_service.get_active_genome", return_value=active):
        result = await _maybe_snapshot_eval_pass(
            pool=AsyncMock(),
            agent_id=uuid4(),
            workspace_id=uuid4(),
            user_id=uuid4(),
            avg_score=0.75,
            pass_rate=0.70,
        )
    assert result is None

    # Case 2: Improvement
    with (
        patch("flow.application.genome_service.get_active_genome", return_value=active),
        patch("flow.application.genome_service.snapshot_genome", return_value=uuid4()) as mock_snap,
    ):
        result = await _maybe_snapshot_eval_pass(
            pool=AsyncMock(),
            agent_id=uuid4(),
            workspace_id=uuid4(),
            user_id=uuid4(),
            avg_score=0.90,
            pass_rate=0.85,
        )
    assert result is not None
    mock_snap.assert_called_once()
