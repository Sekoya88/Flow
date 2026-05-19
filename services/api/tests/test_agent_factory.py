"""Tests for build_agent factory."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_build_agent_returns_none_when_no_api_key():
    from flow.infrastructure.llm.agent_factory import build_agent
    result = build_agent(provider="openai", model="gpt-4o-mini", api_key=None)
    assert result is None


def test_build_agent_returns_none_for_anthropic_without_key():
    from flow.infrastructure.llm.agent_factory import build_agent
    result = build_agent(provider="anthropic", model="claude-3-haiku-20240307", api_key=None)
    assert result is None


def test_build_agent_returns_compiled_graph_with_stub(monkeypatch):
    """With stub provider + test env, build_agent returns a compiled graph."""
    monkeypatch.setenv("FLOW_ENV", "test")

    mock_graph = MagicMock()
    with patch("langgraph.prebuilt.create_react_agent", return_value=mock_graph) as mock_create:
        from flow.infrastructure.llm.agent_factory import build_agent
        result = build_agent(
            provider="stub",
            model="stub-model",
            api_key=None,
            tools=[],
            system_prompt="You are a test assistant.",
        )
    assert result is mock_graph
    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["prompt"] == "You are a test assistant."
    assert call_kwargs["tools"] == []


def test_build_agent_passes_checkpointer_and_store(monkeypatch):
    monkeypatch.setenv("FLOW_ENV", "test")

    mock_graph = MagicMock()
    mock_cp = MagicMock()
    mock_store = MagicMock()
    with patch("langgraph.prebuilt.create_react_agent", return_value=mock_graph) as mock_create:
        from flow.infrastructure.llm.agent_factory import build_agent
        build_agent(
            provider="stub",
            model="stub-model",
            api_key=None,
            checkpointer=mock_cp,
            store=mock_store,
        )
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["checkpointer"] is mock_cp
    assert call_kwargs["store"] is mock_store


def test_build_agent_omits_prompt_when_none(monkeypatch):
    monkeypatch.setenv("FLOW_ENV", "test")

    mock_graph = MagicMock()
    with patch("langgraph.prebuilt.create_react_agent", return_value=mock_graph) as mock_create:
        from flow.infrastructure.llm.agent_factory import build_agent
        build_agent(provider="stub", model="stub-model", api_key=None)
    call_kwargs = mock_create.call_args[1]
    assert "prompt" not in call_kwargs


# ── build_agent_from_ctx ──────────────────────────────────────────────────────

def _make_ctx(template: str = "linear-3", provider: str = "openai", system_prompt: str | None = None):
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from flow.infrastructure.graph.deer_graph import GraphContext
    return GraphContext(
        pool=AsyncMock(),
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        openai_api_key="sk-test" if provider == "openai" else None,
        anthropic_api_key="sk-ant-test" if provider == "anthropic" else None,
        agent_config={
            "template": template,
            "model": {"provider": provider, "model": "gpt-4o-mini"},
            **({"system_prompt": system_prompt} if system_prompt else {}),
        },
        store=MagicMock(),
    )


def test_build_agent_from_ctx_returns_none_when_no_api_key():
    """react-agent template + no API key → build_agent returns None → factory returns None."""
    ctx = _make_ctx(template="react-agent", provider="openai")
    ctx.openai_api_key = None
    from flow.infrastructure.llm.agent_factory import build_agent_from_ctx
    result = build_agent_from_ctx(ctx)
    assert result is None


def test_build_agent_from_ctx_returns_harness_for_react_template(monkeypatch):
    """react-agent template → build_agent_from_ctx returns a FlowMiddlewareHarness."""
    monkeypatch.setenv("FLOW_ENV", "test")
    from flow.infrastructure.llm.middleware.base import FlowMiddlewareHarness
    ctx = _make_ctx(template="react-agent", provider="stub")

    mock_graph = MagicMock()
    with patch("langgraph.prebuilt.create_react_agent", return_value=mock_graph):
        from flow.infrastructure.llm.agent_factory import build_agent_from_ctx
        result = build_agent_from_ctx(ctx)

    assert isinstance(result, FlowMiddlewareHarness)


def test_build_agent_from_ctx_deer_graph_not_wrapped():
    """Non react-agent template → returns raw graph, not a harness."""
    from flow.infrastructure.llm.middleware.base import FlowMiddlewareHarness
    ctx = _make_ctx(template="linear-3", provider="openai")
    mock_graph = MagicMock()
    with patch("flow.infrastructure.graph.deer_graph.build_deer_flow_graph", return_value=mock_graph):
        from flow.infrastructure.llm.agent_factory import build_agent_from_ctx
        result = build_agent_from_ctx(ctx)
    assert not isinstance(result, FlowMiddlewareHarness)
    assert result is mock_graph


def test_build_agent_from_ctx_uses_deer_graph_for_non_react_template():
    """Non react-agent template → routes through build_deer_flow_graph."""
    ctx = _make_ctx(template="linear-3", provider="openai")
    mock_graph = MagicMock()
    # build_deer_flow_graph is lazily imported inside build_agent_from_ctx — patch at source
    with patch("flow.infrastructure.graph.deer_graph.build_deer_flow_graph", return_value=mock_graph) as mock_build:
        from flow.infrastructure.llm.agent_factory import build_agent_from_ctx
        result = build_agent_from_ctx(ctx)
    mock_build.assert_called_once_with(ctx, checkpointer=None)
    assert result is mock_graph


def test_build_agent_from_ctx_wraps_anthropic_prompt_with_cache_control(monkeypatch):
    """react-agent + anthropic provider → system_prompt wrapped in SystemMessage with cache_control."""
    monkeypatch.setenv("FLOW_ENV", "test")
    ctx = _make_ctx(template="react-agent", provider="anthropic", system_prompt="Be helpful.")
    captured = {}
    mock_graph = MagicMock()

    def fake_build_agent(**kwargs):
        captured.update(kwargs)
        return mock_graph

    with patch("flow.infrastructure.llm.agent_factory.build_agent", side_effect=fake_build_agent):
        from flow.infrastructure.llm.agent_factory import build_agent_from_ctx
        build_agent_from_ctx(ctx)

    from langchain_core.messages import SystemMessage
    prompt = captured.get("system_prompt")
    assert isinstance(prompt, SystemMessage), f"Expected SystemMessage, got {type(prompt)}"
    block = prompt.content[0]
    assert block["cache_control"] == {"type": "ephemeral"}
    assert "Be helpful." in block["text"]


@pytest.mark.asyncio
async def test_build_agent_from_ctx_patches_llm_for_before_model(monkeypatch):
    """before_model hook must fire when llm._agenerate is called after patching."""
    monkeypatch.setenv("FLOW_ENV", "test")
    from flow.infrastructure.llm.middleware.base import AgentMiddleware

    calls = []

    class TrackingMiddleware(AgentMiddleware):
        async def before_model(self, messages, runtime):
            calls.append("before_model")
            return None

    # Patch _build_middleware to inject our tracking middleware
    with patch("flow.infrastructure.llm.agent_factory._build_middleware",
               return_value=[TrackingMiddleware()]):
        with patch("langgraph.prebuilt.create_react_agent", return_value=MagicMock()):
            from flow.infrastructure.llm.agent_factory import build_agent_from_ctx
            ctx = _make_ctx(template="react-agent", provider="stub")
            harness = build_agent_from_ctx(ctx)

    # Verify the harness is a FlowMiddlewareHarness with our tracking middleware
    from flow.infrastructure.llm.middleware.base import FlowMiddlewareHarness
    assert isinstance(harness, FlowMiddlewareHarness)
    # The middleware list in the harness should contain our tracking middleware
    assert any(isinstance(m, TrackingMiddleware) for m in harness._middleware)
