"""Subsystem A — profile injection on the deer_flow pipeline.

The default deer_flow pipeline historically ran with NO middleware harness, so the
typed user profile + SOUL.md persona were never injected and no prefs were extracted
after a run. These tests pin the completion:

  1. deer_flow is wrapped in FlowMiddlewareHarness (so before/after_agent run).
  2. the planner folds injected SystemMessages (profile/persona) into its `system`.
  3. with nothing injected, the planner's `system` is byte-identical to before.
  4. the memory middleware (learning loop) is attached when a store is present.
  5. middleware and planner read facts from the SAME namespace tuple.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from flow.infrastructure.graph import nodes as nodes_mod
from flow.infrastructure.graph.deer_graph import GraphContext
from flow.infrastructure.llm.agent_factory import _build_middleware, build_agent_from_ctx
from flow.infrastructure.llm.middleware import FlowMemoryMiddleware, FlowMiddlewareHarness


def _ctx(**over) -> GraphContext:
    base = dict(
        pool=None,
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        openai_api_key=None,
        agent_config={"template": "deer_flow"},
    )
    base.update(over)
    return GraphContext(**base)


class _FakeLLM:
    """Records the messages of the last ainvoke call."""

    def __init__(self) -> None:
        self.captured: list = []

    async def ainvoke(self, messages, *a, **k):
        self.captured = messages

        class _R:
            content = "1. step one"

        return _R()


# ── 1. Harness wrapping ─────────────────────────────────────────────────────────


def test_deer_flow_is_wrapped_in_harness():
    agent = build_agent_from_ctx(_ctx())
    assert isinstance(agent, FlowMiddlewareHarness)


# ── 2 & 3. Planner folds injected SystemMessages ────────────────────────────────


@pytest.mark.asyncio
async def test_planner_folds_injected_profile_into_system(monkeypatch):
    fake = _FakeLLM()
    monkeypatch.setattr(nodes_mod, "_get_llm", lambda ctx: fake)

    planner = nodes_mod.make_planner(_ctx())
    state = {
        "messages": [
            SystemMessage(content="# About the user\n\nBob writes Python."),
            SystemMessage(content="[User Preferences]\nStyle: concise"),
            HumanMessage(content="How do I sort a list?"),
        ]
    }
    await planner(state)

    system = fake.captured[0].content
    assert "About the user" in system
    assert "[User Preferences]" in system
    # The planner's own instruction must still be present.
    assert "planning node" in system


@pytest.mark.asyncio
async def test_planner_system_unchanged_when_nothing_injected(monkeypatch):
    fake = _FakeLLM()
    monkeypatch.setattr(nodes_mod, "_get_llm", lambda ctx: fake)

    planner = nodes_mod.make_planner(_ctx())
    state = {"messages": [HumanMessage(content="How do I sort a list?")]}
    await planner(state)

    system = fake.captured[0].content
    assert system == "You are a planning node. Output a short numbered plan (max 5 bullets)."


# ── 4. Learning loop attached on deer_flow ──────────────────────────────────────


def test_memory_middleware_attached_when_store_present():
    class _Store:  # minimal truthy store
        pass

    middleware = _build_middleware(_ctx(store=_Store()), runtime=None)
    assert any(isinstance(m, FlowMemoryMiddleware) for m in middleware)


# ── 5. Facts namespace consistency ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_middleware_reads_facts_from_string_namespace():
    """Middleware must use the string-form namespace the planner/store writes with."""
    seen: list = []

    class _Store:
        async def asearch(self, ns, *, query, limit):
            seen.append(ns)
            return []

    ws, agent = uuid4(), uuid4()
    from flow.infrastructure.llm.middleware.base import HarnessRuntime

    mw = FlowMemoryMiddleware(store=_Store(), llm=None, embed=None, pool=None)
    runtime = HarnessRuntime(
        workspace_id=ws, agent_id=agent, user_id=uuid4(),
        execution_id=uuid4(), thread_id="t",
    )
    await mw.before_agent({"messages": [HumanMessage(content="hi")]}, runtime)

    assert (str(ws), str(agent), "facts") in seen
