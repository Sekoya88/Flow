import pytest
from unittest.mock import MagicMock


def test_check_prereqs_tavily_missing_key():
    """should return error string when tavily_api_key is not set"""
    from flow.infrastructure.graph.nodes import _check_tool_prereqs

    ctx = MagicMock()
    ctx.settings = MagicMock()
    ctx.settings.tavily_api_key = None

    result = _check_tool_prereqs("tavily_search", ctx)
    assert result is not None
    assert "FLOW_TAVILY_API_KEY" in result


def test_check_prereqs_tavily_key_present():
    """should return None when tavily_api_key is set"""
    from flow.infrastructure.graph.nodes import _check_tool_prereqs

    ctx = MagicMock()
    ctx.settings = MagicMock()
    ctx.settings.tavily_api_key = "tvly-abc123"

    result = _check_tool_prereqs("tavily_search", ctx)
    assert result is None


def test_check_prereqs_unknown_tool():
    """should return None for tools with no prereqs"""
    from flow.infrastructure.graph.nodes import _check_tool_prereqs

    ctx = MagicMock()
    result = _check_tool_prereqs("http_get", ctx)
    assert result is None
