"""Tests for the Self-Harness loop (Zhang et al. 2026) on Flow.

Covers the deterministic core (accept rule, apply_edit, split partition) and the
four stages with mocked LLM / graph / judge / pool: weakness mining, proposal,
validation gate, and orchestration (promote vs all-reject).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def _msg(content: str):
    return MagicMock(content=content)


# ---------------------------------------------------------------------------
# Accept rule (paper's non-regression promotion gate)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "d_in,d_ho,expected",
    [
        (0.1, 0.2, True),  # both improve
        (0.1, 0.0, True),  # improve in, hold out flat
        (0.0, 0.1, True),  # flat in, improve out
        (0.0, 0.0, False),  # no improvement
        (-0.1, 0.3, False),  # held-in regression
        (0.3, -0.1, False),  # held-out regression
    ],
)
def test_accept_rule(d_in, d_ho, expected):
    from flow.application.self_harness.types import accept

    assert accept(d_in, d_ho) is expected


# ---------------------------------------------------------------------------
# apply_edit — pure, per-surface
# ---------------------------------------------------------------------------


def _edit(surface, target, payload):
    from flow.application.self_harness.types import HarnessEdit

    return HarnessEdit(surface=surface, mutation_type="t", target=target, payload=payload)


def test_apply_edit_system_prompt():
    from flow.application.self_harness.mutations import apply_edit

    out = apply_edit({"system_prompt": "old"}, _edit("system_prompt", "system_prompt", {"system_prompt": "new"}))
    assert out["system_prompt"] == "new"


def test_apply_edit_loops():
    from flow.application.self_harness.mutations import apply_edit

    cfg = {"loops": {"max_tool_iters": 8}}
    out = apply_edit(cfg, _edit("loops", "loops:max_tool_iters", {"value": 40}))
    assert out["loops"]["max_tool_iters"] == 40
    assert cfg["loops"]["max_tool_iters"] == 8  # input untouched


def test_apply_edit_tools():
    from flow.application.self_harness.mutations import apply_edit

    out = apply_edit({"tools": {"sandbox": True}}, _edit("tools", "tool:tavily_search", {"enabled": True}))
    assert out["tools"]["tavily_search"] is True
    assert out["tools"]["sandbox"] is True


def test_apply_edit_temperature():
    from flow.application.self_harness.mutations import apply_edit

    out = apply_edit({"llm_config": {"model": "gpt-4o-mini", "temperature": 0.2}}, _edit("temperature", "temperature", {"value": 0.5}))
    assert out["llm_config"]["temperature"] == 0.5


def test_apply_edit_rejects_unknown_surface():
    from flow.application.self_harness.mutations import apply_edit

    with pytest.raises(ValueError):
        apply_edit({}, _edit("skill", "skill:foo", {}))


# ---------------------------------------------------------------------------
# Weakness mining — clustering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mine_weaknesses_clusters_by_signature():
    """should group same-(cause,mechanism) failures and exclude non-addressable ones"""
    from flow.application.self_harness.weakness_miner import mine_weaknesses

    pool = AsyncMock()
    pool.fetch.return_value = [
        {"input_text": "q1", "expected_output": "e", "actual_output": "a", "score": 0.2, "grading_rationale": "no file"},
        {"input_text": "q2", "expected_output": "e", "actual_output": "a", "score": 0.1, "grading_rationale": "no file"},
        {"input_text": "q3", "expected_output": "e", "actual_output": "a", "score": 0.3, "grading_rationale": "too hard"},
    ]
    attributions = (
        '[{"cause":"missing artifact","mechanism":"no output file","surface":"loops","actionability":0.8},'
        '{"cause":"missing artifact","mechanism":"no output file","surface":"loops","actionability":0.6},'
        '{"cause":"hard task","mechanism":"capability limit","surface":"none","actionability":0.1}]'
    )
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=_msg(attributions))

    bundle = await mine_weaknesses(pool, uuid4(), llm=llm)

    assert len(bundle.patterns) == 1  # the "none" surface row is excluded
    p = bundle.patterns[0]
    assert p.support == 2
    assert p.candidate_surface == "loops"


@pytest.mark.asyncio
async def test_mine_weaknesses_empty_without_failures():
    from flow.application.self_harness.weakness_miner import mine_weaknesses

    pool = AsyncMock()
    pool.fetch.return_value = []
    bundle = await mine_weaknesses(pool, uuid4(), llm=MagicMock())
    assert bundle.patterns == []


# ---------------------------------------------------------------------------
# Proposer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_propose_edits_returns_bounded_distinct_edits():
    from flow.application.self_harness.proposer import propose_edits
    from flow.application.self_harness.types import EvidenceBundle, FailurePattern

    bundle = EvidenceBundle(patterns=[FailurePattern("missing artifact", "no output file", 2, "loops", actionability=0.8)])
    edits_json = (
        '[{"surface":"loops","target":"loops:max_tool_iters","payload":{"value":40},'
        '"rationale":"cap runaway tool use","source_pattern":"missing artifact||no output file"}]'
    )
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=_msg(edits_json))

    edits = await propose_edits({"loops": {"max_tool_iters": 8}}, bundle, llm=llm, k=3)

    assert len(edits) == 1
    assert edits[0].surface == "loops"
    assert edits[0].mutation_type == "loops_tune"
    assert edits[0].payload["value"] == 40


# ---------------------------------------------------------------------------
# Validation gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eval_config_on_split_pass_rate():
    from flow.application.self_harness import validator

    items = [{"input_text": "a", "expected_output": "x"}, {"input_text": "b", "expected_output": "y"}]
    with (
        patch.object(validator, "run_harness_on_item", new_callable=AsyncMock, return_value="ans"),
        patch.object(validator, "judge_single", new_callable=AsyncMock, side_effect=[{"score": 0.9}, {"score": 0.4}]),
    ):
        rate = await validator.eval_config_on_split(AsyncMock(), uuid4(), uuid4(), uuid4(), {}, items)
    assert rate == 0.5  # one of two items passed


@pytest.mark.asyncio
async def test_validate_edit_accepts_on_holdout_gain():
    from flow.application.self_harness import validator

    with patch.object(validator, "eval_config_on_split", new_callable=AsyncMock, side_effect=[0.6, 0.7]):
        res = await validator.validate_edit(
            AsyncMock(),
            uuid4(),
            uuid4(),
            uuid4(),
            {"loops": {}},
            _edit("loops", "loops:max_tool_iters", {"value": 40}),
            held_in=[{"input_text": "a"}],
            held_out=[{"input_text": "b"}],
            baseline_in=0.5,
            baseline_ho=0.5,
        )
    assert res["accepted"] is True
    assert round(res["delta_ho"], 3) == 0.2


@pytest.mark.asyncio
async def test_validate_edit_rejects_on_holdout_regression():
    from flow.application.self_harness import validator

    with patch.object(validator, "eval_config_on_split", new_callable=AsyncMock, side_effect=[0.7, 0.4]):
        res = await validator.validate_edit(
            AsyncMock(),
            uuid4(),
            uuid4(),
            uuid4(),
            {"loops": {}},
            _edit("loops", "loops:max_tool_iters", {"value": 40}),
            held_in=[{"input_text": "a"}],
            held_out=[{"input_text": "b"}],
            baseline_in=0.5,
            baseline_ho=0.5,
        )
    assert res["accepted"] is False  # held-out regressed despite held-in gain


# ---------------------------------------------------------------------------
# Split helper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_split_items_partitions():
    from flow.application.self_harness.store import get_split_items

    pool = AsyncMock()
    pool.fetch.return_value = [
        {"input_text": "a", "expected_output": "x", "scoring_criteria": None, "split": "held_in"},
        {"input_text": "b", "expected_output": "y", "scoring_criteria": None, "split": "held_out"},
        {"input_text": "c", "expected_output": "z", "scoring_criteria": None, "split": "held_in"},
    ]
    held_in, held_out = await get_split_items(pool, uuid4())
    assert [i["input_text"] for i in held_in] == ["a", "c"]
    assert [i["input_text"] for i in held_out] == ["b"]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _accepted_validation(edit):
    return {
        "candidate_config": {"loops": {"max_tool_iters": 40}},
        "delta_in": 0.1,
        "delta_ho": 0.2,
        "accepted": True,
        "candidate_pass_in": 0.6,
        "candidate_pass_ho": 0.7,
    }


async def _run_orchestrator(validation_result):
    from flow.application.self_harness import orchestrator
    from flow.application.self_harness.types import EvidenceBundle, FailurePattern, HarnessEdit

    pool = AsyncMock()
    pool.fetchrow.return_value = {"config": {"system_prompt": "p", "loops": {"max_tool_iters": 8}}}

    edit = HarnessEdit("loops", "loops_tune", "loops:max_tool_iters", {"value": 40})
    bundle = EvidenceBundle(patterns=[FailurePattern("c", "m", 2, "loops")])

    with (
        patch.object(orchestrator, "get_split_items", new_callable=AsyncMock, return_value=([{"input_text": "a"}], [{"input_text": "b"}])),
        patch.object(orchestrator, "mine_weaknesses", new_callable=AsyncMock, return_value=bundle),
        patch.object(orchestrator, "propose_edits", new_callable=AsyncMock, return_value=[edit]),
        patch.object(orchestrator, "eval_config_on_split", new_callable=AsyncMock, side_effect=[0.5, 0.5]),
        patch.object(orchestrator, "validate_edit", new_callable=AsyncMock, return_value=validation_result),
        patch.object(orchestrator, "log_edit", new_callable=AsyncMock) as mock_log,
        patch("flow.application.genome_service.snapshot_genome", new_callable=AsyncMock, return_value=uuid4()) as mock_snap,
        patch("flow.application.genome_service.activate_genome", new_callable=AsyncMock) as mock_act,
        patch("flow.application.genome_service.get_active_genome", new_callable=AsyncMock, return_value=MagicMock(id=uuid4())),
    ):
        result = await orchestrator.run_self_harness_round(pool, uuid4(), uuid4(), uuid4(), uuid4())
    return result, mock_log, mock_snap, mock_act


@pytest.mark.asyncio
async def test_orchestrator_promotes_accepted_edit():
    result, mock_log, mock_snap, mock_act = await _run_orchestrator(_accepted_validation(None))

    assert result["status"] == "promoted"
    assert result["n_accepted"] == 1
    mock_log.assert_awaited_once()
    mock_snap.assert_awaited_once()
    mock_act.assert_awaited_once()


@pytest.mark.asyncio
async def test_orchestrator_all_rejected_leaves_genome_untouched():
    rejected = {**_accepted_validation(None), "accepted": False, "delta_in": 0.0, "delta_ho": 0.0}
    result, mock_log, mock_snap, mock_act = await _run_orchestrator(rejected)

    assert result["status"] == "all_rejected"
    mock_log.assert_awaited_once()  # candidate still logged
    mock_snap.assert_not_called()  # no promotion
    mock_act.assert_not_called()


# ---------------------------------------------------------------------------
# Cron flag gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_skips_agents_without_flag(monkeypatch):
    from flow.application.self_harness import orchestrator

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    pool = AsyncMock()
    pool.fetch.return_value = [{"id": uuid4(), "workspace_id": uuid4(), "config": {"system_prompt": "p"}}]  # no flag

    with patch.object(orchestrator, "run_self_harness_round", new_callable=AsyncMock) as mock_round:
        await orchestrator.self_harness_tick({"pool": pool})

    mock_round.assert_not_called()
