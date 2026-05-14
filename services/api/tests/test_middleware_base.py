"""Tests for AgentMiddleware base class and FlowMiddlewareHarness."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


def _make_runtime():
    from flow.infrastructure.llm.middleware.base import HarnessRuntime
    return HarnessRuntime(
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        execution_id=uuid4(),
        thread_id="thread-1",
    )


def _make_stub_graph(chunks: list) -> MagicMock:
    """Stub graph that yields (mode, chunk) tuples and supports aget_state."""
    async def _astream(state, config, **kwargs):
        for item in chunks:
            yield item

    graph = MagicMock()
    graph.astream = _astream
    graph.aget_state = AsyncMock(return_value=MagicMock(values={"answer": "42"}))
    return graph


async def _collect(gen: AsyncGenerator) -> list:
    return [item async for item in gen]


# ── passthrough ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_harness_passes_chunks_through():
    from flow.infrastructure.llm.middleware.base import FlowMiddlewareHarness
    runtime = _make_runtime()
    graph = _make_stub_graph([("updates", {"node": {"answer": "hi"}})])
    harness = FlowMiddlewareHarness(graph, middleware=[], runtime=runtime)
    items = await _collect(harness.astream({"messages": []}, {}))
    assert items == [("updates", {"node": {"answer": "hi"}})]


# ── before_agent order ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_before_agent_runs_in_order():
    from flow.infrastructure.llm.middleware.base import AgentMiddleware, FlowMiddlewareHarness

    calls: list[int] = []

    class M(AgentMiddleware):
        def __init__(self, n):
            self.n = n
        async def before_agent(self, state, runtime):
            calls.append(self.n)
            return state

    runtime = _make_runtime()
    graph = _make_stub_graph([])
    harness = FlowMiddlewareHarness(graph, middleware=[M(1), M(2), M(3)], runtime=runtime)
    await _collect(harness.astream({"messages": []}, {}))
    assert calls == [1, 2, 3]


# ── after_agent fires after stream ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_after_agent_fires_after_stream_exhausted():
    from flow.infrastructure.llm.middleware.base import AgentMiddleware, FlowMiddlewareHarness

    after_called = []

    class M(AgentMiddleware):
        async def after_agent(self, state, runtime):
            after_called.append(state)

    runtime = _make_runtime()
    graph = _make_stub_graph([("updates", {"synthesizer": {"answer": "done"}})])
    harness = FlowMiddlewareHarness(graph, middleware=[M()], runtime=runtime)
    await _collect(harness.astream({"messages": []}, {}))
    assert len(after_called) == 1
    assert after_called[0].get("answer") == "done"


# ── after_agent fires even if generator broken early ─────────────────────────

@pytest.mark.asyncio
async def test_after_agent_fires_on_early_generator_close():
    from flow.infrastructure.llm.middleware.base import AgentMiddleware, FlowMiddlewareHarness

    after_called = []

    class M(AgentMiddleware):
        async def after_agent(self, state, runtime):
            after_called.append(state)

    runtime = _make_runtime()
    graph = _make_stub_graph([
        ("updates", {"node": {"answer": "partial"}}),
        ("updates", {}),
        ("updates", {}),
    ])
    harness = FlowMiddlewareHarness(graph, middleware=[M()], runtime=runtime)

    gen = harness.astream({"messages": []}, {})
    await gen.__anext__()   # consume one chunk then close
    await gen.aclose()

    assert len(after_called) == 1
    # Verify state contains what was accumulated before close
    assert after_called[0].get("answer") == "partial"


# ── after_agent failure doesn't crash ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_after_agent_error_doesnt_crash_run():
    from flow.infrastructure.llm.middleware.base import AgentMiddleware, FlowMiddlewareHarness

    class BrokenM(AgentMiddleware):
        async def after_agent(self, state, runtime):
            raise RuntimeError("broken")

    runtime = _make_runtime()
    graph = _make_stub_graph([("updates", {"n": {"answer": "fine"}})])
    harness = FlowMiddlewareHarness(graph, middleware=[BrokenM()], runtime=runtime)
    items = await _collect(harness.astream({"messages": []}, {}))
    assert len(items) == 1  # chunks still returned despite after_agent failure


# ── aget_state delegates ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_aget_state_delegates_to_graph():
    from flow.infrastructure.llm.middleware.base import FlowMiddlewareHarness
    runtime = _make_runtime()
    graph = _make_stub_graph([])
    harness = FlowMiddlewareHarness(graph, middleware=[], runtime=runtime)
    snap = await harness.aget_state({})
    assert snap.values["answer"] == "42"
