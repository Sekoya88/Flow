"""Custom Prometheus metrics for agent executions.

Wired into ExecutionEventEmitter (single instrumentation point) plus a couple of
direct calls from the execution runner for run-level durations. All recording is
best-effort: a metrics failure must never break an execution.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from prometheus_client import Counter, Histogram, start_http_server

flow_execution_duration_seconds = Histogram(
    "flow_execution_duration_seconds",
    "Wall-clock duration of agent executions",
    ["template", "status"],
    buckets=(0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600),
)

flow_node_duration_seconds = Histogram(
    "flow_node_duration_seconds",
    "Approximate duration of graph nodes (delta between consecutive node_update events)",
    ["node"],
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
)

flow_tool_calls_total = Counter(
    "flow_tool_calls_total",
    "Tool invocations by tool name and outcome",
    ["tool", "status"],
)

flow_tokens_streamed_total = Counter(
    "flow_tokens_streamed_total",
    "Token chunks streamed to clients (SSE)",
)

flow_subagent_runs_total = Counter(
    "flow_subagent_runs_total",
    "Subagent invocations by outcome",
    ["status"],
)

flow_llm_tokens_total = Counter(
    "flow_llm_tokens_total",
    "LLM tokens consumed, by direction (prompt/completion)",
    ["direction"],
)

flow_llm_cost_usd_total = Counter(
    "flow_llm_cost_usd_total",
    "Estimated LLM spend in USD",
)

flow_silent_errors_total = Counter(
    "flow_silent_errors_total",
    "Best-effort observability operations that failed and were swallowed",
    ["where"],
)

# Per-execution timestamp of the last node_update — used to approximate node durations.
# Bounded with a TTL sweep so executions that die without a terminal event
# (final/error/done) cannot leak entries indefinitely.
_last_node_event: dict[str, tuple[str, float]] = {}
_NODE_EVENT_TTL_SECONDS = 3600.0
_NODE_EVENT_MAX = 10_000


def _sweep_stale_node_events(now: float) -> None:
    """Drop tracking entries older than the TTL; hard-cap total size as a backstop."""
    stale = [k for k, (_node, ts) in _last_node_event.items() if now - ts > _NODE_EVENT_TTL_SECONDS]
    for k in stale:
        _last_node_event.pop(k, None)
    if len(_last_node_event) > _NODE_EVENT_MAX:
        # Evict oldest entries first.
        excess = len(_last_node_event) - _NODE_EVENT_MAX
        for k, _ in sorted(_last_node_event.items(), key=lambda kv: kv[1][1])[:excess]:
            _last_node_event.pop(k, None)


def _note_silent_error(where: str) -> None:
    """Count a swallowed best-effort failure so silent errors are observable.

    Must never raise — it runs inside the except blocks it instruments.
    """
    try:
        flow_silent_errors_total.labels(where=where).inc()
    except Exception:
        pass


def record_event(execution_id: UUID | str, kind: str, payload: dict[str, Any]) -> None:
    """Dispatch an execution event to the relevant Prometheus series. Best-effort."""
    try:
        if kind == "node_update":
            key = str(execution_id)
            now = time.monotonic()
            prev = _last_node_event.get(key)
            if prev is not None:
                prev_node, prev_ts = prev
                flow_node_duration_seconds.labels(node=prev_node).observe(max(0.0, now - prev_ts))
            _last_node_event[key] = (str(payload.get("node", "unknown")), now)
            _sweep_stale_node_events(now)
        elif kind == "tool_call":
            flow_tool_calls_total.labels(
                tool=str(payload.get("tool", "unknown")),
                status=str(payload.get("status", "success")),
            ).inc()
        elif kind == "token":
            flow_tokens_streamed_total.inc()
        elif kind == "subagent_done":
            flow_subagent_runs_total.labels(status=str(payload.get("status", "success"))).inc()
        elif kind == "usage":
            flow_llm_tokens_total.labels(direction="prompt").inc(int(payload.get("prompt_tokens") or 0))
            flow_llm_tokens_total.labels(direction="completion").inc(int(payload.get("completion_tokens") or 0))
            cost = payload.get("cost_usd")
            if cost:
                flow_llm_cost_usd_total.inc(float(cost))
        elif kind in ("final", "error", "done"):
            _last_node_event.pop(str(execution_id), None)
    except Exception:
        _note_silent_error("record_event")


def record_execution(template: str, status: str, duration_seconds: float) -> None:
    try:
        flow_execution_duration_seconds.labels(template=template, status=status).observe(duration_seconds)
    except Exception:
        _note_silent_error("record_execution")


def start_metrics_server(port: int) -> bool:
    """Expose /metrics from a non-HTTP process (ARQ worker). Returns False on failure."""
    try:
        start_http_server(port)
        return True
    except Exception:
        return False
