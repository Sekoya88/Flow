"""Tests for best-effort Prometheus metrics: leak bound + silent-error counter."""

from __future__ import annotations

import time
from uuid import uuid4

import pytest

from flow.infrastructure.observability import metrics


@pytest.fixture(autouse=True)
def _clear_tracking():
    metrics._last_node_event.clear()
    yield
    metrics._last_node_event.clear()


def test_node_update_tracks_then_terminal_event_clears() -> None:
    eid = str(uuid4())
    metrics.record_event(eid, "node_update", {"node": "planner"})
    assert eid in metrics._last_node_event
    metrics.record_event(eid, "done", {})
    assert eid not in metrics._last_node_event


def test_stale_entries_are_swept_on_next_node_update() -> None:
    """An execution that dies without a terminal event must not leak forever."""
    dead = str(uuid4())
    metrics.record_event(dead, "node_update", {"node": "worker"})
    # Backdate it beyond the TTL.
    node, _ts = metrics._last_node_event[dead]
    metrics._last_node_event[dead] = (node, time.monotonic() - metrics._NODE_EVENT_TTL_SECONDS - 1)

    # Any later node_update triggers the sweep.
    alive = str(uuid4())
    metrics.record_event(alive, "node_update", {"node": "planner"})

    assert dead not in metrics._last_node_event
    assert alive in metrics._last_node_event


def test_hard_cap_evicts_oldest() -> None:
    now = time.monotonic()
    for i in range(metrics._NODE_EVENT_MAX + 50):
        metrics._last_node_event[f"e{i}"] = ("n", now + i)
    metrics._sweep_stale_node_events(now + metrics._NODE_EVENT_MAX + 100)
    assert len(metrics._last_node_event) <= metrics._NODE_EVENT_MAX


def test_silent_error_counter_increments_on_bad_payload() -> None:
    """A malformed usage payload is swallowed but counted, not invisible."""
    before = metrics.flow_silent_errors_total.labels(where="record_event")._value.get()
    # cost_usd that cannot cast to float forces the except path.
    metrics.record_event(str(uuid4()), "usage", {"prompt_tokens": 1, "completion_tokens": 1, "cost_usd": "not-a-number"})
    after = metrics.flow_silent_errors_total.labels(where="record_event")._value.get()
    assert after == before + 1


def test_note_silent_error_never_raises() -> None:
    # Smoke: helper must be safe to call from inside except blocks.
    metrics._note_silent_error("unit-test")
