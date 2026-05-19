"""Tests for FlowObservabilityMiddleware."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage


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
async def test_wrap_model_call_logs_latency_and_returns_response():
    from flow.infrastructure.llm.middleware.observability import FlowObservabilityMiddleware

    mock_logger = MagicMock()
    mw = FlowObservabilityMiddleware(logger=mock_logger)

    fake_response = MagicMock()
    fake_response.generations = [[MagicMock(message=AIMessage(content="answer"))]]

    async def invoke(msgs):
        return fake_response

    result = await mw.wrap_model_call(invoke, [HumanMessage(content="q")])
    assert result is fake_response
    mock_logger.info.assert_called()
    call_kwargs = mock_logger.info.call_args[1]
    assert "latency_ms" in call_kwargs
    assert "input_tokens" in call_kwargs
    assert "output_tokens" in call_kwargs


@pytest.mark.asyncio
async def test_wrap_tool_call_logs_success():
    from flow.infrastructure.llm.middleware.observability import FlowObservabilityMiddleware

    mock_logger = MagicMock()
    mw = FlowObservabilityMiddleware(logger=mock_logger)

    async def invoke(args):
        return "tool result"

    result = await mw.wrap_tool_call(invoke, {"input": "x"})
    assert result == "tool result"
    mock_logger.info.assert_called()


@pytest.mark.asyncio
async def test_wrap_tool_call_logs_error_and_reraises():
    from flow.infrastructure.llm.middleware.observability import FlowObservabilityMiddleware

    mock_logger = MagicMock()
    mw = FlowObservabilityMiddleware(logger=mock_logger)

    async def invoke(args):
        raise ValueError("tool broke")

    with pytest.raises(ValueError, match="tool broke"):
        await mw.wrap_tool_call(invoke, {})

    mock_logger.error.assert_called()
    call_kwargs = mock_logger.error.call_args[1]
    assert "duration_ms" in call_kwargs
