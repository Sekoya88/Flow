"""Tests for build_agent factory."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


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
    import os
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
    import os
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
    import os
    monkeypatch.setenv("FLOW_ENV", "test")

    mock_graph = MagicMock()
    with patch("langgraph.prebuilt.create_react_agent", return_value=mock_graph) as mock_create:
        from flow.infrastructure.llm.agent_factory import build_agent
        build_agent(provider="stub", model="stub-model", api_key=None)
    call_kwargs = mock_create.call_args[1]
    assert "prompt" not in call_kwargs
