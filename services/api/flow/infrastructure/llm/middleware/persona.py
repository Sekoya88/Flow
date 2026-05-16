"""SOUL.md persona injection — slot #1 of every agent's system prompt.

Mirrors Hermes Agent's pattern: a single durable identity block goes FIRST,
before dynamic memory facts or per-agent system prompts. The user authors
(or regenerates) it from /settings/profile; we just read & inject.
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import SystemMessage

from flow.infrastructure.llm.middleware.base import AgentMiddleware, HarnessRuntime
from flow.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class FlowPersonaMiddleware(AgentMiddleware):
    """Inject the user's SOUL.md as the very first SystemMessage in state."""

    def __init__(self, pool: Any | None) -> None:
        self._pool = pool

    async def before_agent(self, state: dict, runtime: HarnessRuntime) -> dict:
        if self._pool is None:
            return state
        try:
            row = await self._pool.fetchrow(
                "SELECT content_md FROM user_personas "
                "WHERE workspace_id = $1 AND user_id = $2",
                runtime.workspace_id,
                runtime.user_id,
            )
        except Exception as exc:
            logger.warning("persona.before_agent.fetch_failed", error=str(exc))
            return state

        if not row:
            return state
        content = (row["content_md"] or "").strip()
        if not content:
            return state

        block = f"# About the user\n\n{content}"
        msgs = state.get("messages", [])
        return {**state, "messages": [SystemMessage(content=block), *msgs]}
