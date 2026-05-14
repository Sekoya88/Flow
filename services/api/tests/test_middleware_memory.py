"""Tests for FlowMemoryMiddleware."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


def _make_runtime():
    from flow.infrastructure.llm.middleware.base import HarnessRuntime
    return HarnessRuntime(
        workspace_id=uuid4(), agent_id=uuid4(),
        user_id=uuid4(), execution_id=uuid4(), thread_id="t1",
    )


def _make_store(facts=None, patterns=None):
    store = AsyncMock()
    async def asearch(ns, query=None, limit=8):
        if "facts" in ns:
            return [MagicMock(value={"text": f}) for f in (facts or [])]
        if "patterns" in ns:
            return [MagicMock(value={"problem": p, "solution": "s"}) for p in (patterns or [])]
        return []
    store.asearch = asearch
    store.aput = AsyncMock()
    return store


# ── before_agent ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_before_agent_prepends_system_message_when_facts_exist():
    from flow.infrastructure.llm.middleware.memory import FlowMemoryMiddleware
    store = _make_store(facts=["User prefers bullet lists"])
    mw = FlowMemoryMiddleware(store=store, llm=None, embed=None)
    runtime = _make_runtime()
    state = {"messages": [HumanMessage(content="hello")]}
    result = await mw.before_agent(state, runtime)
    assert isinstance(result["messages"][0], SystemMessage)
    assert "User prefers bullet lists" in result["messages"][0].content


@pytest.mark.asyncio
async def test_before_agent_noop_when_store_empty():
    from flow.infrastructure.llm.middleware.memory import FlowMemoryMiddleware
    store = _make_store(facts=[], patterns=[])
    mw = FlowMemoryMiddleware(store=store, llm=None, embed=None)
    runtime = _make_runtime()
    state = {"messages": [HumanMessage(content="hello")]}
    result = await mw.before_agent(state, runtime)
    assert result is state  # exact same object — no mutation


# ── after_agent ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_after_agent_stores_extracted_facts():
    from flow.infrastructure.llm.middleware.memory import FlowMemoryMiddleware
    store = _make_store()
    embed = AsyncMock(return_value=[0.1, 0.2])
    llm = MagicMock()

    with patch(
        "flow.infrastructure.llm.middleware.memory.extract_facts_from_answer",
        new=AsyncMock(return_value=["user likes Python"]),
    ):
        mw = FlowMemoryMiddleware(store=store, llm=llm, embed=embed)
        runtime = _make_runtime()
        state = {"answer": "Python is great", "confidence": 0.9,
                 "messages": [HumanMessage(content="q"), AIMessage(content="Python is great")]}
        await mw.after_agent(state, runtime)

    store.aput.assert_called()
    call_args = store.aput.call_args_list[0]
    ns = call_args[0][0]
    assert "facts" in ns


@pytest.mark.asyncio
async def test_after_agent_skips_pattern_below_confidence():
    from flow.infrastructure.llm.middleware.memory import FlowMemoryMiddleware
    store = _make_store()
    embed = AsyncMock(return_value=[0.1])

    with patch(
        "flow.infrastructure.llm.middleware.memory.extract_facts_from_answer",
        new=AsyncMock(return_value=["some fact"]),
    ), patch(
        "flow.infrastructure.llm.middleware.memory.extract_pattern_summary",
        new=AsyncMock(return_value=("problem", "solution")),
    ) as mock_pattern:
        mw = FlowMemoryMiddleware(store=store, llm=MagicMock(), embed=embed, min_confidence=0.7)
        runtime = _make_runtime()
        state = {"answer": "ok", "confidence": 0.5,
                 "messages": [HumanMessage(content="q"), AIMessage(content="ok")]}
        await mw.after_agent(state, runtime)

    mock_pattern.assert_not_called()


@pytest.mark.asyncio
async def test_after_agent_noop_when_no_llm():
    from flow.infrastructure.llm.middleware.memory import FlowMemoryMiddleware
    store = _make_store()
    mw = FlowMemoryMiddleware(store=store, llm=None, embed=None)
    runtime = _make_runtime()
    await mw.after_agent({"answer": "x", "messages": []}, runtime)
    store.aput.assert_not_called()
