"""Tests for multi-tier memory: decay, reinforcement, compression, pruning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from flow.application import memory_compaction as mc


def _ts(days_ago: float, now: datetime) -> str:
    return (now - timedelta(days=days_ago)).isoformat()


def test_new_fact_has_lifecycle_fields() -> None:
    f = mc.new_fact("user prefers Python", emb=[0.1])
    assert f["text"] == "user prefers Python"
    assert f["score"] == mc._INITIAL_SCORE
    assert f["created_at"] and f["last_used_at"]
    assert f["pinned"] is False


def test_effective_score_decays_over_time() -> None:
    now = datetime.now(tz=UTC)
    fresh = mc.new_fact("x")
    aged = mc.new_fact("y")
    aged["last_used_at"] = _ts(60, now)  # 2 half-lives (30d) old
    assert mc.fact_effective_score(fresh, now=now) > mc.fact_effective_score(aged, now=now)
    # Two half-lives → ~0.25 of original score.
    assert mc.fact_effective_score(aged, now=now) == pytest.approx(mc._INITIAL_SCORE * 0.25, rel=0.05)


def test_pinned_fact_does_not_decay() -> None:
    now = datetime.now(tz=UTC)
    f = mc.new_fact("important")
    f["pinned"] = True
    f["last_used_at"] = _ts(365, now)
    assert mc.fact_effective_score(f, now=now) == f["score"]


def test_reinforce_bumps_score_and_recency() -> None:
    now = datetime.now(tz=UTC)
    f = mc.new_fact("x")
    f["last_used_at"] = _ts(10, now)
    r = mc.reinforce(f, now=now)
    assert r["score"] > f["score"]
    assert r["last_used_at"] > f["last_used_at"]


def test_reinforce_caps_at_max() -> None:
    f = mc.new_fact("x")
    f["score"] = 0.95
    assert mc.reinforce(f)["score"] <= mc._MAX_SCORE


def test_select_for_compression_by_age_skips_pinned() -> None:
    now = datetime.now(tz=UTC)
    old = mc.new_fact("old")
    old["created_at"] = _ts(30, now)
    pinned_old = mc.new_fact("pinned")
    pinned_old["created_at"] = _ts(30, now)
    pinned_old["pinned"] = True
    recent = mc.new_fact("recent")
    recent["created_at"] = _ts(1, now)

    selected = mc.select_for_compression([old, pinned_old, recent], now=now)
    texts = {f["text"] for f in selected}
    assert texts == {"old"}


def test_select_for_prune_drops_faded_unpinned() -> None:
    now = datetime.now(tz=UTC)
    faded = mc.new_fact("faded")
    faded["score"] = 0.5
    faded["last_used_at"] = _ts(120, now)  # 4 half-lives → ~0.03
    pinned_faded = mc.new_fact("pinned")
    pinned_faded["score"] = 0.01
    pinned_faded["pinned"] = True
    fresh = mc.new_fact("fresh")

    to_prune = mc.select_for_prune([faded, pinned_faded, fresh], now=now)
    assert {f["text"] for f in to_prune} == {"faded"}


# ── Orchestration with a fake store ─────────────────────────────────────────


class _Item:
    def __init__(self, key, value):
        self.key = key
        self.value = value


class _FakeStore:
    def __init__(self):
        self.data: dict[tuple, dict[str, dict]] = {}

    async def asearch(self, namespace, *, query=None, limit=1000):
        return [_Item(k, v) for k, v in self.data.get(namespace, {}).items()]

    async def aput(self, namespace, key, value):
        self.data.setdefault(namespace, {})[key] = value

    async def adelete(self, namespace, key):
        self.data.get(namespace, {}).pop(key, None)


class _FakeLLM:
    async def ainvoke(self, messages):
        class _R:
            content = "- summary bullet one\n- summary bullet two"

        return _R()


@pytest.mark.asyncio
async def test_compact_namespace_summarizes_and_prunes() -> None:
    now = datetime.now(tz=UTC)
    store = _FakeStore()
    facts_ns = ("ws", "agent", "facts")
    summaries_ns = ("ws", "agent", "summaries")

    # 6 aging facts (eligible for compression) + 1 faded (prune) + 1 fresh (keep).
    for i in range(6):
        f = mc.new_fact(f"aging fact {i}")
        f["created_at"] = _ts(30, now)
        f["last_used_at"] = _ts(5, now)  # not faded enough to prune
        store.data.setdefault(facts_ns, {})[f"aging{i}"] = f

    faded = mc.new_fact("faded fact")
    faded["last_used_at"] = _ts(200, now)
    faded["created_at"] = _ts(200, now)
    store.data[facts_ns]["faded"] = faded

    fresh = mc.new_fact("fresh fact")
    store.data[facts_ns]["fresh"] = fresh

    result = await mc.compact_namespace(store, facts_ns, summaries_ns, llm=_FakeLLM(), now=now)

    assert result["summaries"] == 1
    assert result["compressed"] == 6
    assert result["pruned"] >= 1
    # A TIER 2 summary was written.
    assert len(store.data.get(summaries_ns, {})) == 1
    # The fresh fact survived; aging facts were folded away.
    surviving = {v["text"] for v in store.data[facts_ns].values()}
    assert "fresh fact" in surviving
    assert not any(t.startswith("aging fact") for t in surviving)


@pytest.mark.asyncio
async def test_compact_namespace_noop_when_too_few_facts() -> None:
    now = datetime.now(tz=UTC)
    store = _FakeStore()
    facts_ns = ("ws", "agent", "facts")
    summaries_ns = ("ws", "agent", "summaries")
    f = mc.new_fact("lonely aging fact")
    f["created_at"] = _ts(30, now)
    f["last_used_at"] = _ts(5, now)
    store.data[facts_ns] = {"a": f}

    result = await mc.compact_namespace(store, facts_ns, summaries_ns, llm=_FakeLLM(), now=now)
    assert result["summaries"] == 0
    assert result["compressed"] == 0
