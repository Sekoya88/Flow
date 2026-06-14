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

# Per-execution timestamp of the last node_update — used to approximate node durations.
_last_node_event: dict[str, tuple[str, float]] = {}


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
        pass


def record_execution(template: str, status: str, duration_seconds: float) -> None:
    try:
        flow_execution_duration_seconds.labels(template=template, status=status).observe(duration_seconds)
    except Exception:
        pass


def start_metrics_server(port: int) -> bool:
    """Expose /metrics from a non-HTTP process (ARQ worker). Returns False on failure."""
    try:
        start_http_server(port)
        return True
    except Exception:
        return False
