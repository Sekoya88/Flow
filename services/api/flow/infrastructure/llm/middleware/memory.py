from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

from flow.application.memory_judge import extract_facts_from_answer, extract_pattern_summary
from flow.application.preference_service import (
    auto_graduate,
    effective_score,
    extract_preferences,
)
from flow.infrastructure.llm.middleware.base import AgentMiddleware, HarnessRuntime
from flow.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)

_MAX_PER_CLASS = 3


def _stable_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def _format_memory_block(facts: list, patterns: list) -> str:
    lines = ["[Memory from previous runs]"]
    if facts:
        lines.append("Facts:")
        for f in facts:
            lines.append(f"  • {f.value.get('text', '')}")
    if patterns:
        lines.append("Patterns:")
        for p in patterns:
            lines.append(f"  • {p.value.get('problem', '')} → {p.value.get('solution', '')}")
    return "\n".join(lines)


def _format_profile_block(rows: list) -> str | None:
    """Build [User Preferences] system message from active/provisional rows."""
    from collections import defaultdict
    by_class: dict[str, list] = defaultdict(list)

    for row in rows:
        cls = row["class"]
        val = row["value"]
        eff = effective_score(
            row["score"],
            row["last_reinforced_at"],
            row["decay_half_life_days"],
            row.get("pinned", False),
        )
        label = f"{val} (learning)" if row["status"] == "provisional" else val
        by_class[cls].append((eff, label))

    if not by_class:
        return None

    lines = ["[User Preferences]"]
    for cls in ["style", "tooling", "goal", "veto", "domain", "channel"]:
        if cls not in by_class:
            continue
        entries = sorted(by_class[cls], key=lambda x: -x[0])[:_MAX_PER_CLASS]
        lines.append(f"{cls.capitalize()}: {'; '.join(e[1] for e in entries)}")

    return "\n".join(lines)


class FlowMemoryMiddleware(AgentMiddleware):
    """Inject cross-run facts + user preferences before each run; extract both after."""

    def __init__(
        self,
        store: Any,
        llm: Any | None,
        embed: Callable[[str], Awaitable] | None,
        pool: Any | None = None,
        max_facts: int = 8,
        min_confidence: float = 0.7,
    ) -> None:
        self._store = store
        self._llm = llm
        self._embed = embed
        self._pool = pool
        self._max_facts = max_facts
        self._min_confidence = min_confidence
        self._stashed_question: str = ""

    async def before_agent(self, state: dict, runtime: HarnessRuntime) -> dict:
        messages = state.get("messages", [])
        if not messages:
            return state

        self._stashed_question = next(
            (getattr(m, "content", "") for m in messages
             if not isinstance(m, (AIMessage, SystemMessage))),
            "",
        )

        query = next(
            (getattr(m, "content", "") for m in reversed(messages)
             if not isinstance(m, (AIMessage, SystemMessage))),
            "",
        )[:200]

        prepend: list = []

        # Inject user profile if pool available
        if self._pool:
            try:
                from flow.infrastructure.persistence.repo import FlowRepository
                repo = FlowRepository(self._pool)
                profile_rows = await repo.load_profile(
                    runtime.workspace_id, runtime.user_id, runtime.agent_id
                )
                block = _format_profile_block(profile_rows)
                if block:
                    prepend.append(SystemMessage(content=block))
            except Exception as exc:
                logger.warning("memory.before_agent.profile_failed", error=str(exc))

        ns_facts = (runtime.workspace_id, runtime.agent_id, "facts")
        ns_patterns = (runtime.workspace_id, runtime.agent_id, "patterns")

        try:
            facts = await self._store.asearch(ns_facts, query=query, limit=self._max_facts)
            patterns = await self._store.asearch(ns_patterns, query=query, limit=3)
            if facts or patterns:
                prepend.append(SystemMessage(content=_format_memory_block(facts, patterns)))
        except Exception as exc:
            logger.warning("memory.before_agent.search_failed", error=str(exc))

        if not prepend:
            return state
        return {**state, "messages": prepend + messages}

    async def after_agent(self, state: dict, runtime: HarnessRuntime) -> None:
        if not self._llm:
            return

        messages = state.get("messages", [])
        answer = state.get("answer") or next(
            (getattr(m, "content", "") for m in reversed(messages)
             if isinstance(m, AIMessage)),
            "",
        )
        question = self._stashed_question
        if not answer:
            return

        # Extract and store facts
        ns_facts = (runtime.workspace_id, runtime.agent_id, "facts")
        try:
            facts = await extract_facts_from_answer(self._llm, question, answer)
            for fact in facts:
                key = _stable_key(fact)
                emb = await self._embed(fact) if self._embed else None
                await self._store.aput(ns_facts, key, {"text": fact, "emb": emb})
        except Exception as exc:
            logger.warning("memory.after_agent.extract_failed", error=str(exc))

        # Extract and upsert preferences
        if self._pool:
            try:
                from flow.infrastructure.persistence.repo import FlowRepository
                conversation = f"Q: {question}\nA: {answer}"
                prefs = await extract_preferences(self._llm, conversation)
                repo = FlowRepository(self._pool)
                for pref in prefs:
                    row = await repo.upsert_typed_preference(
                        runtime.workspace_id, runtime.user_id,
                        pref["class"], pref["value"],
                        runtime.agent_id,
                    )
                    new_status = auto_graduate(dict(row))
                    if new_status:
                        await repo.apply_preference_graduation(row["id"], new_status)
            except Exception as exc:
                logger.warning("memory.after_agent.prefs_failed", error=str(exc))

        # Pattern extraction (only if high confidence)
        confidence = float(state.get("confidence") or 0.0)
        if confidence < self._min_confidence:
            return

        try:
            pattern = await extract_pattern_summary(self._llm, question, answer)
            if pattern:
                problem, solution = pattern
                ns_pat = (runtime.workspace_id, runtime.agent_id, "patterns")
                await self._store.aput(
                    ns_pat, _stable_key(problem), {"problem": problem, "solution": solution}
                )
        except Exception as exc:
            logger.warning("memory.after_agent.pattern_failed", error=str(exc))
