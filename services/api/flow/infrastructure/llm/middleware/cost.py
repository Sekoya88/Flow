from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from flow.infrastructure.llm.middleware.base import AgentMiddleware, HarnessRuntime
from flow.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


def _tiktoken_counter(messages: list[BaseMessage]) -> int:
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return sum(len(enc.encode(getattr(m, "content", "") or "")) for m in messages)
    except Exception:
        return sum(len(getattr(m, "content", "") or "") // 4 for m in messages)


class FlowCostMiddleware(AgentMiddleware):
    """Count LLM calls; summarize conversation when token threshold is exceeded."""

    def __init__(
        self,
        token_limit: int = 80_000,
        call_limit: int = 30,
        summarize_model: Any = None,
        token_counter: Callable[[list[BaseMessage]], int] = _tiktoken_counter,
    ) -> None:
        self._token_limit = token_limit
        self._call_limit = call_limit
        self._summarize_model = summarize_model
        self._token_counter = token_counter
        self._call_count: int = 0

    async def before_model(
        self, messages: list[BaseMessage], runtime: HarnessRuntime
    ) -> dict | list | None:
        self._call_count += 1

        if self._call_count > self._call_limit:
            logger.warning(
                "cost.call_limit_reached",
                call_count=self._call_count,
                limit=self._call_limit,
            )
            return {"jump_to": "end"}

        if not messages:
            return None

        token_count = self._token_counter(messages)
        if token_count <= self._token_limit:
            return None

        # Summarize: keep last 4 messages intact; summarize the rest
        if len(messages) <= 4 or not self._summarize_model:
            return None

        to_summarize = messages[:-4]
        keep = messages[-4:]

        try:
            summary_prompt = (
                "Summarize the following conversation in 3-5 bullet points, "
                "preserving key facts and decisions:\n\n"
                + "\n".join(
                    f"{type(m).__name__}: {getattr(m, 'content', '')[:500]}"
                    for m in to_summarize
                )
            )
            summary_resp = await self._summarize_model.ainvoke([HumanMessage(content=summary_prompt)])
            summary_text = getattr(summary_resp, "content", str(summary_resp))
            summarized = [AIMessage(content=f"[Earlier conversation summary]\n{summary_text}")] + keep
            logger.info(
                "cost.summarized",
                removed=len(to_summarize),
                tokens_before=token_count,
            )
            return summarized
        except Exception as exc:
            logger.warning("cost.summarize_failed", error=str(exc))
            return None
