"""Tests for loop-engineering / metacognition closed loops.

Covers the three feedback loops wired in this change:
  A — bandit-driven skill selection (SkillLoader.load_and_match)
  C — progress-aware loops (reflector regression guard, worker carry-forward,
      tool_agent oscillation break)
  D — mistakes fed forward (reflector -> agent_negatives)
plus the shared `_loops_cfg` flag resolver.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def _ctx(agent_config=None, execution_id=None):
    from flow.infrastructure.graph.deer_graph import GraphContext

    return GraphContext(
        pool=AsyncMock(),
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        openai_api_key=None,
        agent_config=agent_config if agent_config is not None else {},
        execution_id=execution_id,
    )


def _msg(content: str):
    """Canned LLM message whose `.content` carries the reflector JSON / answer."""
    return MagicMock(content=content)


# ---------------------------------------------------------------------------
# Shared flag resolver
# ---------------------------------------------------------------------------


def test_loops_cfg_defaults_all_on():
    """should default every loop flag ON when agent_config has no `loops` block"""
    from flow.infrastructure.graph.nodes import _loops_cfg

    cfg = _loops_cfg(_ctx())
    assert cfg["bandit_selection"] is True
    assert cfg["progress_guard"] is True
    assert cfg["feed_mistakes_forward"] is True
    assert cfg["max_tool_iters"] == 8
    assert cfg["max_retries"] == 2


def test_loops_cfg_honors_overrides():
    """should override only the provided keys and keep defaults for the rest"""
    from flow.infrastructure.graph.nodes import _loops_cfg

    cfg = _loops_cfg(_ctx({"loops": {"bandit_selection": False, "max_tool_iters": 3}}))
    assert cfg["bandit_selection"] is False
    assert cfg["max_tool_iters"] == 3
    assert cfg["progress_guard"] is True  # untouched default


# ---------------------------------------------------------------------------
# A — bandit-driven skill selection
# ---------------------------------------------------------------------------


def _skill_loader_with_two_skills():
    """A SkillLoader whose repo yields a low-score and a high-score skill."""
    from flow.application.skill_loader import SkillLoader

    id_low, id_high = uuid4(), uuid4()
    repo = AsyncMock()
    repo.list_active_skills.return_value = [
        {"id": id_low, "content_md": "low", "score": 0.1, "use_count": 0},
        {"id": id_high, "content_md": "high", "score": 0.9, "use_count": 0},
    ]
    return SkillLoader(repo), id_low, id_high


def _parsed(name):
    from flow.application.skill_parser import ParsedSkill

    return ParsedSkill(name=name)


@pytest.mark.asyncio
async def test_load_and_match_uses_bandit_order_when_enabled():
    """should order matched skills by the bandit, not raw score, when use_bandit=True"""
    loader, id_low, id_high = _skill_loader_with_two_skills()

    with (
        patch("flow.application.skill_loader.parse_skill_md", side_effect=lambda md: _parsed(md)),
        patch("flow.application.skill_loader.skill_matches_query", return_value=True),
        patch("flow.application.rl_bandit.SkillBandit") as MockBandit,
    ):
        # Bandit prefers the LOW-score skill — the opposite of static ranking.
        MockBandit.return_value.select_skills = AsyncMock(return_value=[id_low, id_high])

        matched = await loader.load_and_match(uuid4(), uuid4(), "query", use_bandit=True)

    assert [m.skill_id for m in matched] == [id_low, id_high]


@pytest.mark.asyncio
async def test_load_and_match_static_order_when_bandit_disabled():
    """should fall back to score DESC when use_bandit=False"""
    loader, id_low, id_high = _skill_loader_with_two_skills()

    with (
        patch("flow.application.skill_loader.parse_skill_md", side_effect=lambda md: _parsed(md)),
        patch("flow.application.skill_loader.skill_matches_query", return_value=True),
        patch("flow.application.rl_bandit.SkillBandit") as MockBandit,
    ):
        matched = await loader.load_and_match(uuid4(), uuid4(), "query", use_bandit=False)

    MockBandit.assert_not_called()
    assert [m.skill_id for m in matched] == [id_high, id_low]  # score DESC


@pytest.mark.asyncio
async def test_load_and_match_falls_back_when_bandit_raises():
    """should keep the static score order if the bandit blows up (best-effort)"""
    loader, id_low, id_high = _skill_loader_with_two_skills()

    with (
        patch("flow.application.skill_loader.parse_skill_md", side_effect=lambda md: _parsed(md)),
        patch("flow.application.skill_loader.skill_matches_query", return_value=True),
        patch("flow.application.rl_bandit.SkillBandit") as MockBandit,
    ):
        MockBandit.return_value.select_skills = AsyncMock(side_effect=RuntimeError("db down"))
        matched = await loader.load_and_match(uuid4(), uuid4(), "query", use_bandit=True)

    assert [m.skill_id for m in matched] == [id_high, id_low]


# ---------------------------------------------------------------------------
# C1 — reflector regression guard
# ---------------------------------------------------------------------------


async def _run_reflector(state, llm_grade_json, agent_config=None):
    from flow.infrastructure.graph.nodes import make_reflector

    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=_msg(llm_grade_json))

    with (
        patch("flow.infrastructure.graph.nodes.FlowRepository") as MockRepo,
        patch("flow.infrastructure.graph.nodes._get_llm", return_value=llm),
    ):
        repo = AsyncMock()
        repo.list_agent_negatives.return_value = []
        MockRepo.return_value = repo
        reflector = make_reflector(_ctx(agent_config))
        result = await reflector(state)
    return result, repo


@pytest.mark.asyncio
async def test_reflector_retries_when_low_grade_and_no_regression():
    """should retry, carry prior_answer, and append critique on a first low grade"""
    answer = "B" * 150
    state = {"answer": answer, "retry_count": 0, "plan": "p", "messages": [MagicMock(type="human", content="q")]}

    result, _ = await _run_reflector(state, '{"grade": 2, "prediction": "x", "issue": "too vague"}')

    assert result["retry_count"] == 1
    assert result["prior_answer"] == answer
    assert "Reflector critique" in result["plan"]
    assert result["best_grade"] == 2


@pytest.mark.asyncio
async def test_reflector_stops_and_surfaces_best_on_regression():
    """should not retry when a later attempt regresses, and surface the earlier best answer"""
    best = "GOOD" * 40
    state = {
        "answer": "C" * 150,  # current (worse) attempt
        "retry_count": 1,
        "best_grade": 4,
        "best_answer": best,
        "plan": "p",
        "messages": [MagicMock(type="human", content="q")],
    }

    result, _ = await _run_reflector(state, '{"grade": 2, "prediction": "x", "issue": "worse"}')

    assert result.get("retry_count") is None  # did NOT retry
    assert result["answer"] == best  # earlier, higher-graded answer wins
    assert result["best_grade"] == 4


@pytest.mark.asyncio
async def test_reflector_legacy_loop_when_progress_guard_off():
    """should still bound-retry on grade<=2 with progress_guard disabled (no best tracking)"""
    state = {"answer": "B" * 150, "retry_count": 0, "plan": "p", "messages": [MagicMock(type="human", content="q")]}

    result, _ = await _run_reflector(
        state,
        '{"grade": 1, "prediction": "x", "issue": "bad"}',
        agent_config={"loops": {"progress_guard": False}},
    )

    assert result["retry_count"] == 1
    assert "best_grade" not in result  # progress tracking disabled


# ---------------------------------------------------------------------------
# D — mistakes fed forward
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reflector_records_negative_on_low_grade():
    """should insert a reflector agent_negative when grade<=2 and an issue is present"""
    state = {"answer": "B" * 150, "retry_count": 0, "plan": "p", "messages": [MagicMock(type="human", content="q")]}

    _, repo = await _run_reflector(state, '{"grade": 2, "prediction": "x", "issue": "missed the constraint"}')

    repo.insert_agent_negative.assert_called_once()
    assert repo.insert_agent_negative.call_args.kwargs["source"] == "reflector"


@pytest.mark.asyncio
async def test_reflector_dedupes_existing_negative():
    """should skip inserting a near-duplicate reflector negative"""
    from flow.infrastructure.graph.nodes import make_reflector

    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=_msg('{"grade": 2, "prediction": "x", "issue": "missed the constraint"}'))
    state = {"answer": "B" * 150, "retry_count": 0, "plan": "p", "messages": [MagicMock(type="human", content="q")]}

    with (
        patch("flow.infrastructure.graph.nodes.FlowRepository") as MockRepo,
        patch("flow.infrastructure.graph.nodes._get_llm", return_value=llm),
    ):
        repo = AsyncMock()
        repo.list_agent_negatives.return_value = [{"content": "missed the constraint earlier", "source": "reflector"}]
        MockRepo.return_value = repo
        await make_reflector(_ctx())(state)

    repo.insert_agent_negative.assert_not_called()


@pytest.mark.asyncio
async def test_reflector_no_negative_on_good_grade():
    """should not record a negative when the answer graded well"""
    state = {"answer": "B" * 150, "retry_count": 0, "plan": "p", "messages": [MagicMock(type="human", content="q")]}

    _, repo = await _run_reflector(state, '{"grade": 5, "prediction": "x", "issue": null}')

    repo.insert_agent_negative.assert_not_called()


# ---------------------------------------------------------------------------
# C2 — worker carries the rejected answer forward
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_injects_prior_answer_on_retry():
    """should include the rejected prior_answer in the worker prompt so it revises"""
    from flow.infrastructure.graph.nodes import make_worker

    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=_msg("revised answer"))

    with (
        patch("flow.infrastructure.graph.nodes.FlowRepository") as MockRepo,
        patch("flow.infrastructure.graph.nodes._rag_and_memory", new_callable=AsyncMock) as mock_rag,
        patch("flow.infrastructure.graph.nodes._get_llm", return_value=llm),
    ):
        repo = AsyncMock()
        repo.load_profile.return_value = []
        repo.list_agent_negatives.return_value = []
        MockRepo.return_value = repo
        mock_rag.return_value = ([], [], [])

        state = {
            "plan": "p",
            "prior_answer": "OLD REJECTED ANSWER",
            "messages": [MagicMock(type="human", content="q")],
        }
        await make_worker(_ctx())(state)

    human_content = llm.ainvoke.call_args.args[0][1].content
    assert "previous attempt was rejected" in human_content
    assert "OLD REJECTED ANSWER" in human_content


@pytest.mark.asyncio
async def test_worker_no_retry_block_without_prior_answer():
    """should not add the revise hint on a fresh run"""
    from flow.infrastructure.graph.nodes import make_worker

    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=_msg("answer"))

    with (
        patch("flow.infrastructure.graph.nodes.FlowRepository") as MockRepo,
        patch("flow.infrastructure.graph.nodes._rag_and_memory", new_callable=AsyncMock) as mock_rag,
        patch("flow.infrastructure.graph.nodes._get_llm", return_value=llm),
    ):
        repo = AsyncMock()
        repo.load_profile.return_value = []
        repo.list_agent_negatives.return_value = []
        MockRepo.return_value = repo
        mock_rag.return_value = ([], [], [])

        await make_worker(_ctx())({"plan": "p", "messages": [MagicMock(type="human", content="q")]})

    human_content = llm.ainvoke.call_args.args[0][1].content
    assert "previous attempt was rejected" not in human_content


# ---------------------------------------------------------------------------
# C3 — tool_agent oscillation / no-progress break
# ---------------------------------------------------------------------------


def _tool(name="search", result="ok"):
    tool = MagicMock()
    tool.name = name
    tool.arun = AsyncMock(return_value=result)
    return tool


def _bound_llm(side_effect=None, return_value=None):
    bound = MagicMock()
    bound.ainvoke = AsyncMock(side_effect=side_effect, return_value=return_value)
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=bound)
    return llm, bound


@pytest.mark.asyncio
async def test_tool_agent_breaks_on_oscillation():
    """should stop once every tool call repeats a signature already executed"""
    from flow.infrastructure.graph.nodes import make_tool_agent

    tool = _tool()
    resp = MagicMock()
    resp.tool_calls = [{"name": "search", "args": {"q": "x"}, "id": "1"}]
    resp.content = "thinking"
    llm, bound = _bound_llm(return_value=resp)  # identical call every turn

    with (
        patch("flow.infrastructure.graph.nodes._build_context_tools", new_callable=AsyncMock) as mock_tools,
        patch("flow.infrastructure.graph.nodes._get_llm", return_value=llm),
    ):
        mock_tools.return_value = [tool]
        await make_tool_agent(_ctx())({"messages": [MagicMock(type="human", content="q")]})

    # iter 1 executes; iter 2 sees the same signature -> break. Never reaches 8.
    assert bound.ainvoke.call_count == 2
    assert tool.arun.call_count == 1


@pytest.mark.asyncio
async def test_tool_agent_respects_max_iters_override():
    """should cap iterations at the configured max_tool_iters when calls keep progressing"""
    from flow.infrastructure.graph.nodes import make_tool_agent

    tool = _tool()
    counter = {"n": 0}

    async def fresh_call(_msgs):
        counter["n"] += 1
        r = MagicMock()
        r.tool_calls = [{"name": "search", "args": {"q": counter["n"]}, "id": str(counter["n"])}]
        r.content = "t"
        return r

    llm, bound = _bound_llm(side_effect=fresh_call)

    with (
        patch("flow.infrastructure.graph.nodes._build_context_tools", new_callable=AsyncMock) as mock_tools,
        patch("flow.infrastructure.graph.nodes._get_llm", return_value=llm),
    ):
        mock_tools.return_value = [tool]
        ctx = _ctx({"loops": {"max_tool_iters": 3}})
        await make_tool_agent(ctx)({"messages": [MagicMock(type="human", content="q")]})

    assert bound.ainvoke.call_count == 3  # distinct sigs -> runs to the cap
