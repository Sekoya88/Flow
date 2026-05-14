from __future__ import annotations

import hashlib
from collections.abc import Callable, Awaitable
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

from flow.application.memory_judge import extract_facts_from_answer, extract_pattern_summary
from flow.infrastructure.llm.middleware.base import AgentMiddleware, HarnessRuntime
from flow.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


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


class FlowMemoryMiddleware(AgentMiddleware):
    """Inject cross-run facts before each run; extract and store facts after."""

    def __init__(
        self,
        store: Any,
        llm: Any | None,
        embed: Callable[[str], Awaitable] | None,
        max_facts: int = 8,
        min_confidence: float = 0.7,
    ) -> None:
        self._store = store
        self._llm = llm
        self._embed = embed
        self._max_facts = max_facts
        self._min_confidence = min_confidence

    async def before_agent(self, state: dict, runtime: HarnessRuntime) -> dict:
        messages = state.get("messages", [])
        if not messages:
            return state

        query = next(
            (getattr(m, "content", "") for m in reversed(messages)
             if not isinstance(m, (AIMessage, SystemMessage))),
            "",
        )[:200]
        ns_facts = (runtime.workspace_id, runtime.agent_id, "facts")
        ns_patterns = (runtime.workspace_id, runtime.agent_id, "patterns")

        try:
            facts = await self._store.asearch(ns_facts, query=query, limit=self._max_facts)
            patterns = await self._store.asearch(ns_patterns, query=query, limit=3)
        except Exception as exc:
            logger.warning("memory.before_agent.search_failed", error=str(exc))
            return state

        if not facts and not patterns:
            return state

        memory_block = _format_memory_block(facts, patterns)
        return {**state, "messages": [SystemMessage(content=memory_block)] + messages}

    async def after_agent(self, state: dict, runtime: HarnessRuntime) -> None:
        if not self._llm:
            return

        messages = state.get("messages", [])
        answer = state.get("answer") or next(
            (getattr(m, "content", "") for m in reversed(messages)
             if isinstance(m, AIMessage)),
            "",
        )
        question = next(
            (getattr(m, "content", "") for m in messages
             if not isinstance(m, (AIMessage, SystemMessage))),
            "",
        )
        if not answer:
            return

        ns_facts = (runtime.workspace_id, runtime.agent_id, "facts")
        try:
            facts = await extract_facts_from_answer(self._llm, question, answer)
            for fact in facts:
                key = _stable_key(fact)
                emb = await self._embed(fact) if self._embed else None
                await self._store.aput(ns_facts, key, {"text": fact, "emb": emb})
        except Exception as exc:
            logger.warning("memory.after_agent.extract_failed", error=str(exc))
            return

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
