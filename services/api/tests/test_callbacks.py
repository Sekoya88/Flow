"""Tests for FlowCallbackHandler structured observability."""
from __future__ import annotations

import logging
import time
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from langchain_core.outputs import LLMResult


@pytest.fixture
def handler():
    from flow.infrastructure.observability.callbacks import FlowCallbackHandler
    return FlowCallbackHandler(
        workspace_id="ws-1",
        agent_id="agent-1",
        execution_id="exec-1",
        template="linear-3",
    )


def test_on_llm_start_logs_model_and_records_time(handler):
    run_id = uuid4()
    serialized = {"name": "ChatOpenAI", "kwargs": {"model_name": "gpt-4o"}}
    handler.on_llm_start(serialized, ["Hello"], run_id=run_id)
    assert run_id in handler._llm_start_times


def test_on_llm_end_removes_timing_entry(handler):
    run_id = uuid4()
    handler._llm_start_times[run_id] = time.monotonic()
    response = LLMResult(generations=[[]])
    handler.on_llm_end(response, run_id=run_id)
    assert run_id not in handler._llm_start_times


def test_on_llm_error_removes_timing_entry(handler):
    run_id = uuid4()
    handler._llm_start_times[run_id] = time.monotonic()
    handler.on_llm_error(ValueError("timeout"), run_id=run_id)
    assert run_id not in handler._llm_start_times


def test_on_tool_start_records_time(handler):
    run_id = uuid4()
    serialized = {"name": "search"}
    handler.on_tool_start(serialized, "query text", run_id=run_id)
    assert run_id in handler._tool_start_times


def test_on_tool_end_removes_timing_entry(handler):
    run_id = uuid4()
    handler._tool_start_times[run_id] = time.monotonic()
    handler.on_tool_end("result", run_id=run_id)
    assert run_id not in handler._tool_start_times


def test_on_tool_error_removes_timing_entry(handler):
    run_id = uuid4()
    handler._tool_start_times[run_id] = time.monotonic()
    handler.on_tool_error(RuntimeError("fail"), run_id=run_id)
    assert run_id not in handler._tool_start_times


def test_elapsed_ms_returns_minus_one_when_no_start(handler):
    run_id = uuid4()
    result = handler._elapsed_ms({}, run_id)
    assert result == -1.0


def test_elapsed_ms_returns_positive_float(handler):
    run_id = uuid4()
    store = {run_id: time.monotonic() - 0.1}
    result = handler._elapsed_ms(store, run_id)
    assert result > 0


def test_context_fields_omitted_when_none():
    from flow.infrastructure.observability.callbacks import FlowCallbackHandler
    h = FlowCallbackHandler()
    assert "workspace_id" not in h._ctx
    assert "agent_id" not in h._ctx


def test_context_fields_present_when_provided(handler):
    assert handler._ctx["workspace_id"] == "ws-1"
    assert handler._ctx["template"] == "linear-3"


def test_on_llm_end_includes_token_usage(handler):
    """LLMResult with token_usage emits token fields without error."""
    run_id = uuid4()
    handler._llm_start_times[run_id] = time.monotonic()
    response = LLMResult(
        generations=[[]],
        llm_output={"token_usage": {"prompt_tokens": 10, "completion_tokens": 20}},
    )
    # Should not raise
    handler.on_llm_end(response, run_id=run_id)


def test_on_chain_error_does_not_raise(handler):
    handler.on_chain_error(Exception("boom"), run_id=uuid4())
