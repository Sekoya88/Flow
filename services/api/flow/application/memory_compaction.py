"""Multi-tier memory: decay, reinforcement, compression, pruning.

Flow stores cross-run agent memory as facts in a LangGraph ``AsyncPostgresStore``
(a namespaced KV store). Left unbounded, facts accumulate every run and overflow
the planner's context. This module adds a lifecycle on top of the flat store:

  TIER 1  episodic  — individual facts, scored, decaying over time
  TIER 2  semantic  — LLM summaries of aging facts (compact, long-lived)

The scoring/decay reuses the same half-life model as user preferences
(:func:`flow.application.preference_service.effective_score`), so a fact that is
recalled often stays salient and a stale fact fades and is eventually pruned.

The pure functions here are store-agnostic and fully testable. The single
I/O-bound orchestrator, :func:`compact_namespace`, is given the store and an LLM
and is exercised in tests with a fake store.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from flow.application.preference_service import effective_score

# Defaults for a freshly extracted fact.
_INITIAL_SCORE = 0.6
_DEFAULT_HALF_LIFE_DAYS = 30
_REINFORCE_BUMP = 0.15
_MAX_SCORE = 1.0

# Lifecycle thresholds.
COMPRESS_AGE_DAYS = 14  # facts older than this are eligible for summarization
PRUNE_SCORE_THRESHOLD = 0.15  # effective score below this (and unpinned) → drop
MIN_FACTS_TO_COMPRESS = 5  # don't summarize a handful of facts


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _parse_dt(value: Any, *, default: datetime | None = None) -> datetime:
    """Best-effort parse of an ISO timestamp stored in a fact value."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            pass
    return default or _now()


def new_fact(text: str, emb: Any = None, *, now: datetime | None = None) -> dict[str, Any]:
    """Build an enriched fact record for storage (TIER 1)."""
    ts = (now or _now()).isoformat()
    return {
        "text": text,
        "emb": emb,
        "score": _INITIAL_SCORE,
        "created_at": ts,
        "last_used_at": ts,
        "decay_half_life_days": _DEFAULT_HALF_LIFE_DAYS,
        "pinned": False,
    }


def fact_effective_score(fact: dict[str, Any], *, now: datetime | None = None) -> float:
    """Current salience of a fact under time decay. Tolerant of legacy records."""
    score = float(fact.get("score", _INITIAL_SCORE))
    last_used = _parse_dt(fact.get("last_used_at") or fact.get("created_at"))
    half_life = int(fact.get("decay_half_life_days", _DEFAULT_HALF_LIFE_DAYS)) or _DEFAULT_HALF_LIFE_DAYS
    pinned = bool(fact.get("pinned", False))
    # effective_score reads "now" itself; for testability we re-derive when now given.
    if now is None:
        return effective_score(score, last_used, half_life, pinned)
    if pinned:
        return score
    if last_used.tzinfo is None:
        last_used = last_used.replace(tzinfo=UTC)
    days = (now - last_used).total_seconds() / 86400
    return score * (0.5 ** (days / half_life))


def reinforce(fact: dict[str, Any], *, now: datetime | None = None, bump: float = _REINFORCE_BUMP) -> dict[str, Any]:
    """Return a copy of *fact* with refreshed recency and a bumped score."""
    updated = dict(fact)
    updated["last_used_at"] = (now or _now()).isoformat()
    updated["score"] = min(_MAX_SCORE, float(fact.get("score", _INITIAL_SCORE)) + bump)
    return updated


def select_for_compression(
    facts: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    age_days: int = COMPRESS_AGE_DAYS,
) -> list[dict[str, Any]]:
    """Facts old enough to fold into a summary. Pinned facts are never compressed."""
    now = now or _now()
    out = []
    for f in facts:
        if f.get("pinned"):
            continue
        created = _parse_dt(f.get("created_at"))
        if (now - created).total_seconds() / 86400 >= age_days:
            out.append(f)
    return out


def select_for_prune(
    facts: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    threshold: float = PRUNE_SCORE_THRESHOLD,
) -> list[dict[str, Any]]:
    """Faded, unpinned facts whose effective score dropped below the threshold."""
    now = now or _now()
    return [f for f in facts if not f.get("pinned") and fact_effective_score(f, now=now) < threshold]


_SUMMARY_PROMPT = """\
You are compressing an AI agent's long-term memory. Below are individual facts
learned across past runs. Write a concise summary (max 200 words) that preserves
the durable, reusable knowledge and drops run-specific noise. Use short bullet
points. Do not invent facts.

Facts:
{facts}"""


async def summarize_facts(llm: Any, facts: list[dict[str, Any]]) -> str | None:
    """LLM-compress a batch of facts into a single TIER 2 summary. None on failure."""
    if not facts or llm is None:
        return None
    joined = "\n".join(f"- {f.get('text', '')}" for f in facts if f.get("text"))
    if not joined:
        return None
    from langchain_core.messages import HumanMessage

    try:
        out = await llm.ainvoke([HumanMessage(content=_SUMMARY_PROMPT.format(facts=joined[:6000]))])
        text = str(out.content).strip()
        return text or None
    except Exception:
        return None


def new_summary(text: str, *, source_count: int, now: datetime | None = None) -> dict[str, Any]:
    """Build a TIER 2 summary record."""
    ts = (now or _now()).isoformat()
    return {"text": text, "tier": "semantic", "source_count": source_count, "created_at": ts}


async def store_memory_view(
    store: Any,
    facts_ns: tuple[str, ...],
    summaries_ns: tuple[str, ...],
    *,
    now: datetime | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Read-only transparency view of an agent's tiered store memory.

    Returns facts (TIER 1) with their current decay-adjusted salience, sorted
    most-salient first, plus the compressed summaries (TIER 2). Powers a
    "what does this agent remember, and how strongly" UI.
    """
    now = now or _now()
    facts_items = await store.asearch(facts_ns, query=None, limit=limit)
    try:
        summary_items = await store.asearch(summaries_ns, query=None, limit=50)
    except Exception:
        summary_items = []

    facts = []
    for it in facts_items:
        v = getattr(it, "value", None)
        if not v:
            continue
        facts.append(
            {
                "key": getattr(it, "key", None),
                "text": v.get("text", ""),
                "score": float(v.get("score", _INITIAL_SCORE)),
                "effective_score": round(fact_effective_score(v, now=now), 4),
                "pinned": bool(v.get("pinned", False)),
                "created_at": v.get("created_at"),
                "last_used_at": v.get("last_used_at"),
            }
        )
    facts.sort(key=lambda f: f["effective_score"], reverse=True)

    summaries = [
        {
            "key": getattr(it, "key", None),
            "text": (getattr(it, "value", None) or {}).get("text", ""),
            "source_count": (getattr(it, "value", None) or {}).get("source_count", 0),
            "created_at": (getattr(it, "value", None) or {}).get("created_at"),
        }
        for it in summary_items
        if getattr(it, "value", None)
    ]

    return {"facts": facts, "summaries": summaries}


class _Store(Protocol):
    async def asearch(self, namespace: tuple[str, ...], *, query: str | None = ..., limit: int = ...) -> list[Any]: ...
    async def aput(self, namespace: tuple[str, ...], key: str, value: dict) -> Any: ...
    async def adelete(self, namespace: tuple[str, ...], key: str) -> Any: ...


async def compact_namespace(
    store: _Store,
    facts_ns: tuple[str, ...],
    summaries_ns: tuple[str, ...],
    *,
    llm: Any,
    now: datetime | None = None,
) -> dict[str, int]:
    """Run one compaction pass over a single agent's fact namespace.

    1. Prune faded, unpinned facts.
    2. If enough aging facts remain, summarize them into TIER 2 and delete the
       sources.

    Returns counts: ``{"pruned": n, "compressed": n, "summaries": n}``.
    Best-effort: individual store failures are swallowed so a bad fact can't
    abort the whole pass.
    """
    now = now or _now()
    items = await store.asearch(facts_ns, query=None, limit=1000)
    facts = [{**it.value, "_key": it.key} for it in items if getattr(it, "value", None)]

    to_prune = select_for_prune(facts, now=now)
    pruned_keys = {f["_key"] for f in to_prune}
    pruned = 0
    for f in to_prune:
        try:
            await store.adelete(facts_ns, f["_key"])
            pruned += 1
        except Exception:
            pass

    remaining = [f for f in facts if f["_key"] not in pruned_keys]
    to_compress = select_for_compression(remaining, now=now)

    compressed = 0
    summaries = 0
    if len(to_compress) >= MIN_FACTS_TO_COMPRESS:
        summary_text = await summarize_facts(llm, to_compress)
        if summary_text:
            import hashlib

            key = hashlib.sha256(summary_text.encode()).hexdigest()[:32]
            try:
                await store.aput(summaries_ns, key, new_summary(summary_text, source_count=len(to_compress), now=now))
                summaries = 1
                for f in to_compress:
                    try:
                        await store.adelete(facts_ns, f["_key"])
                        compressed += 1
                    except Exception:
                        pass
            except Exception:
                pass

    return {"pruned": pruned, "compressed": compressed, "summaries": summaries}
