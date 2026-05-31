"""Tests that graph nodes read from and write to AsyncPostgresStore via ctx.store."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_planner_does_not_read_store_directly():
    """Phase 2: facts are injected by FlowMemoryMiddleware, not read inline by the planner.

    The planner must not call store.asearch itself anymore — that read moved to the
    middleware's before_agent (which injects facts as SystemMessages the planner folds in).
    """
    from langchain_core.messages import HumanMessage

    from flow.infrastructure.graph.deer_graph import GraphContext
    from flow.infrastructure.graph.nodes import make_planner

    mock_store = AsyncMock()
    mock_store.asearch = AsyncMock(return_value=[])

    ctx = GraphContext(
        pool=AsyncMock(),
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        openai_api_key=None,
        agent_config={},
        store=mock_store,
    )
    planner = make_planner(ctx)
    state = {"messages": [HumanMessage(content="What is RAG?")]}
    await planner(state)

    mock_store.asearch.assert_not_awaited()


@pytest.mark.asyncio
async def test_planner_skips_store_when_store_is_none():
    """Planner does not fail when ctx.store is None."""
    from langchain_core.messages import HumanMessage

    from flow.infrastructure.graph.deer_graph import GraphContext
    from flow.infrastructure.graph.nodes import make_planner

    ctx = GraphContext(
        pool=AsyncMock(),
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        openai_api_key=None,
        agent_config={},
        store=None,
    )
    planner = make_planner(ctx)
    state = {"messages": [HumanMessage(content="What is RAG?")]}
    result = await planner(state)
    assert "plan" in result


@pytest.mark.asyncio
async def test_synthesizer_writes_store_facts_when_store_present():
    """Synthesizer node calls store.aput when ctx.store is set and LLM returns an answer."""
    from unittest.mock import patch

    from langchain_core.messages import AIMessage, HumanMessage

    from flow.infrastructure.graph.deer_graph import GraphContext
    from flow.infrastructure.graph.nodes import make_synthesizer

    mock_store = AsyncMock()
    mock_store.aput = AsyncMock()

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="The answer is 42. CONFIDENCE: 0.9"))

    ctx = GraphContext(
        pool=AsyncMock(),
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        openai_api_key="sk-test",  # non-None so LLM path is taken
        agent_config={},
        store=mock_store,
    )
    synthesizer = make_synthesizer(ctx)
    state = {
        "messages": [HumanMessage(content="question")],
        "plan": "step 1. do thing",
        "worker_output": "some notes",
    }

    with patch("flow.infrastructure.graph.nodes._get_llm", return_value=mock_llm):
        result = await synthesizer(state)

    assert "answer" in result
    mock_store.aput.assert_awaited()
    put_args = mock_store.aput.call_args
    namespace = put_args[0][0] if put_args[0] else put_args[1].get("namespace")
    assert "facts" in namespace


@pytest.mark.asyncio
async def test_synthesizer_skips_store_when_store_is_none():
    """Synthesizer does not fail when ctx.store is None."""
    from langchain_core.messages import HumanMessage

    from flow.infrastructure.graph.deer_graph import GraphContext
    from flow.infrastructure.graph.nodes import make_synthesizer

    ctx = GraphContext(
        pool=AsyncMock(),
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        openai_api_key=None,
        agent_config={},
        store=None,
    )
    synthesizer = make_synthesizer(ctx)
    state = {
        "messages": [HumanMessage(content="question")],
        "plan": "plan",
        "worker_output": "notes",
    }
    result = await synthesizer(state)
    assert "answer" in result
