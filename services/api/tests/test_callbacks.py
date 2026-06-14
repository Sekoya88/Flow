"""Tests for FlowCallbackHandler structured observability."""

from __future__ import annotations

import time
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


# ── Cost estimation ────────────────────────────────────────────────────────


def test_estimate_cost_usd_known_model():
    from flow.infrastructure.observability.callbacks import _estimate_cost_usd

    # gpt-4o-mini: (0.15, 0.60) per 1M tokens → 1000 in + 500 out
    cost = _estimate_cost_usd("gpt-4o-mini", 1000, 500)
    assert cost == round((1000 * 0.15 + 500 * 0.60) / 1_000_000, 6)


def test_estimate_cost_usd_matches_by_prefix():
    from flow.infrastructure.observability.callbacks import _estimate_cost_usd

    # Provider often suffixes a date/version — prefix match must still resolve.
    assert _estimate_cost_usd("gpt-4o-mini-2024-07-18", 1000, 0) is not None


def test_estimate_cost_usd_unknown_model_returns_none():
    from flow.infrastructure.observability.callbacks import _estimate_cost_usd

    assert _estimate_cost_usd("some-unknown-model", 1000, 500) is None


# ── Usage event emission ───────────────────────────────────────────────────


class _SpyEmitter:
    def __init__(self):
        self.events: list[tuple] = []

    def emit_nowait(self, execution_id, kind, payload):
        self.events.append((execution_id, kind, payload))


def test_on_llm_end_emits_usage_event_with_cost():
    from flow.infrastructure.observability.callbacks import FlowCallbackHandler

    emitter = _SpyEmitter()
    exec_uuid = uuid4()
    h = FlowCallbackHandler(execution_id=str(exec_uuid), emitter=emitter)
    run_id = uuid4()
    h.on_llm_start({"kwargs": {"model_name": "gpt-4o-mini"}}, ["hi"], run_id=run_id)
    response = LLMResult(
        generations=[[]],
        llm_output={"token_usage": {"prompt_tokens": 1000, "completion_tokens": 500}},
    )
    h.on_llm_end(response, run_id=run_id)

    assert len(emitter.events) == 1
    eid, kind, payload = emitter.events[0]
    assert eid == exec_uuid
    assert kind == "usage"
    assert payload["model"] == "gpt-4o-mini"
    assert payload["prompt_tokens"] == 1000
    assert payload["completion_tokens"] == 500
    assert "cost_usd" in payload


def test_no_usage_event_without_token_usage():
    from flow.infrastructure.observability.callbacks import FlowCallbackHandler

    emitter = _SpyEmitter()
    h = FlowCallbackHandler(execution_id=str(uuid4()), emitter=emitter)
    run_id = uuid4()
    h._llm_start_times[run_id] = time.monotonic()
    h.on_llm_end(LLMResult(generations=[[]]), run_id=run_id)
    assert emitter.events == []


def test_invalid_execution_id_disables_emission():
    from flow.infrastructure.observability.callbacks import FlowCallbackHandler

    emitter = _SpyEmitter()
    h = FlowCallbackHandler(execution_id="not-a-uuid", emitter=emitter)
    assert h._execution_id is None
    run_id = uuid4()
    h._llm_start_times[run_id] = time.monotonic()
    response = LLMResult(
        generations=[[]],
        llm_output={"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}},
    )
    h.on_llm_end(response, run_id=run_id)
    assert emitter.events == []
