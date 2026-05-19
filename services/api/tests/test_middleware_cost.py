"""Tests for FlowCostMiddleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage


def _make_runtime():
    from flow.infrastructure.llm.middleware.base import HarnessRuntime

    return HarnessRuntime(
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        execution_id=uuid4(),
        thread_id="t1",
    )


@pytest.mark.asyncio
async def test_before_model_increments_call_count():
    from flow.infrastructure.llm.middleware.cost import FlowCostMiddleware

    mw = FlowCostMiddleware(
        token_limit=999_999,
        call_limit=10,
        summarize_model=MagicMock(),
        token_counter=lambda msgs: 10,
    )
    runtime = _make_runtime()
    messages = [HumanMessage(content="hi")]
    await mw.before_model(messages, runtime)
    await mw.before_model(messages, runtime)
    assert mw._call_count == 2


@pytest.mark.asyncio
async def test_before_model_returns_jump_to_end_at_limit():
    from flow.infrastructure.llm.middleware.cost import FlowCostMiddleware

    mw = FlowCostMiddleware(
        token_limit=999_999,
        call_limit=2,
        summarize_model=MagicMock(),
        token_counter=lambda msgs: 10,
    )
    runtime = _make_runtime()
    messages = [HumanMessage(content="hi")]
    await mw.before_model(messages, runtime)
    await mw.before_model(messages, runtime)
    result = await mw.before_model(messages, runtime)
    assert result == {"jump_to": "end"}


@pytest.mark.asyncio
async def test_before_model_summarizes_when_over_token_limit():
    from flow.infrastructure.llm.middleware.cost import FlowCostMiddleware

    summarized = "Summary of earlier conversation."
    summarize_model = AsyncMock()
    summarize_model.ainvoke = AsyncMock(return_value=MagicMock(content=summarized))

    messages = [HumanMessage(content="q" * 200)] * 10 + [HumanMessage(content="latest")]

    def token_counter(msgs):
        return len(msgs) * 100  # 11 msgs = 1100 tokens

    mw = FlowCostMiddleware(
        token_limit=500,
        call_limit=100,
        summarize_model=summarize_model,
        token_counter=token_counter,
    )
    runtime = _make_runtime()
    result = await mw.before_model(messages, runtime)
    # Should have summarized — result is the modified messages list
    assert result is not None
    assert summarize_model.ainvoke.called
    # Result should be shorter than original messages
    assert len(result) < len(messages)


@pytest.mark.asyncio
async def test_before_model_noop_when_under_limit():
    from flow.infrastructure.llm.middleware.cost import FlowCostMiddleware

    mw = FlowCostMiddleware(
        token_limit=999_999,
        call_limit=100,
        summarize_model=MagicMock(),
        token_counter=lambda msgs: 5,
    )
    runtime = _make_runtime()
    messages = [HumanMessage(content="hi")]
    result = await mw.before_model(messages, runtime)
    assert result is None  # no mutation


@pytest.mark.asyncio
async def test_before_model_noop_when_over_limit_but_too_few_messages():
    """Should not summarize when over token limit but <= 4 messages (not enough to summarize)."""
    from flow.infrastructure.llm.middleware.cost import FlowCostMiddleware

    summarize_model = AsyncMock()
    mw = FlowCostMiddleware(
        token_limit=10,
        call_limit=100,
        summarize_model=summarize_model,
        token_counter=lambda msgs: 9999,  # always over limit
    )
    runtime = _make_runtime()
    messages = [HumanMessage(content="hi"), HumanMessage(content="bye")]  # only 2 messages
    result = await mw.before_model(messages, runtime)
    assert result is None  # can't summarize — too few messages
    summarize_model.ainvoke.assert_not_called()
