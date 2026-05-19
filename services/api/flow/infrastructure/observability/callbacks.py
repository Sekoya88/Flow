"""LangChain callback handler for structured observability (model + tool events)."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from flow.infrastructure.observability.logging import get_logger

_log = get_logger("flow.llm")


class FlowCallbackHandler(BaseCallbackHandler):
    """Emits structlog events for LLM and tool lifecycle, with latency tracking."""

    def __init__(
        self,
        *,
        workspace_id: str | None = None,
        agent_id: str | None = None,
        execution_id: str | None = None,
        template: str | None = None,
    ) -> None:
        super().__init__()
        self._ctx = {
            k: v
            for k, v in {
                "workspace_id": workspace_id,
                "agent_id": agent_id,
                "execution_id": execution_id,
                "template": template,
            }.items()
            if v is not None
        }
        self._llm_start_times: dict[UUID, float] = {}
        self._tool_start_times: dict[UUID, float] = {}

    # ── LLM events ──────────────────────────────────────────────────────

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._llm_start_times[run_id] = time.monotonic()
        model = serialized.get("kwargs", {}).get("model_name") or serialized.get("name", "unknown")
        _log.info("llm.start", model=model, prompt_count=len(prompts), **self._ctx)

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        elapsed_ms = self._elapsed_ms(self._llm_start_times, run_id)
        token_usage = {}
        if response.llm_output:
            usage = response.llm_output.get("token_usage") or response.llm_output.get("usage", {})
            if usage:
                token_usage = {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                }
        _log.info("llm.end", latency_ms=elapsed_ms, **token_usage, **self._ctx)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        elapsed_ms = self._elapsed_ms(self._llm_start_times, run_id)
        _log.error("llm.error", error=str(error), latency_ms=elapsed_ms, **self._ctx)

    # ── Tool events ──────────────────────────────────────────────────────

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._tool_start_times[run_id] = time.monotonic()
        tool_name = serialized.get("name", "unknown")
        _log.info("tool.start", tool=tool_name, **self._ctx)

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        elapsed_ms = self._elapsed_ms(self._tool_start_times, run_id)
        _log.info("tool.end", latency_ms=elapsed_ms, **self._ctx)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        elapsed_ms = self._elapsed_ms(self._tool_start_times, run_id)
        _log.error("tool.error", error=str(error), latency_ms=elapsed_ms, **self._ctx)

    # ── Chain error ──────────────────────────────────────────────────────

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        _log.error("chain.error", error=str(error), **self._ctx)

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _elapsed_ms(store: dict[UUID, float], run_id: UUID) -> float:
        start = store.pop(run_id, None)
        return round((time.monotonic() - start) * 1000, 1) if start is not None else -1.0
