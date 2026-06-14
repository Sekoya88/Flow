"""LangChain callback handler for structured observability (model + tool events)."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from flow.infrastructure.observability.logging import get_logger

_log = get_logger("flow.llm")

# Indicative USD prices per 1M tokens (prompt, completion). Best-effort estimate
# for the /logs cost column — not a billing source of truth.
_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-sonnet-4": (3.00, 15.00),
}


def _estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    for prefix, (p_in, p_out) in _PRICE_PER_MTOK.items():
        if model.startswith(prefix):
            return round((prompt_tokens * p_in + completion_tokens * p_out) / 1_000_000, 6)
    return None


class FlowCallbackHandler(BaseCallbackHandler):
    """Emits structlog events for LLM and tool lifecycle, with latency tracking.

    When an ExecutionEventEmitter + execution_id are provided, also persists a
    `usage` event per LLM call (tokens in/out, latency, estimated cost) so the
    /logs page can aggregate per-execution spend.
    """

    def __init__(
        self,
        *,
        workspace_id: str | None = None,
        agent_id: str | None = None,
        execution_id: str | None = None,
        template: str | None = None,
        emitter: Any | None = None,
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
        self._emitter = emitter
        try:
            self._execution_id: UUID | None = UUID(execution_id) if execution_id else None
        except (ValueError, TypeError):
            self._execution_id = None
        self._llm_start_times: dict[UUID, float] = {}
        self._llm_models: dict[UUID, str] = {}
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
        self._llm_models[run_id] = str(model)
        _log.info("llm.start", model=model, prompt_count=len(prompts), **self._ctx)

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        elapsed_ms = self._elapsed_ms(self._llm_start_times, run_id)
        model = self._llm_models.pop(run_id, "unknown")
        token_usage = {}
        if response.llm_output:
            usage = response.llm_output.get("token_usage") or response.llm_output.get("usage", {})
            if usage:
                token_usage = {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                }
        # Fallback: usage_metadata on the generated message (langchain >= 0.2 chat models)
        if not token_usage:
            try:
                gen = response.generations[0][0]
                meta = getattr(getattr(gen, "message", None), "usage_metadata", None)
                if meta:
                    token_usage = {
                        "prompt_tokens": int(meta.get("input_tokens", 0)),
                        "completion_tokens": int(meta.get("output_tokens", 0)),
                    }
            except Exception:
                pass
        _log.info("llm.end", model=model, latency_ms=elapsed_ms, **token_usage, **self._ctx)

        if self._emitter is not None and self._execution_id is not None and token_usage:
            cost = _estimate_cost_usd(model, token_usage["prompt_tokens"], token_usage["completion_tokens"])
            payload = {
                "model": model,
                "latency_ms": elapsed_ms,
                **token_usage,
            }
            if cost is not None:
                payload["cost_usd"] = cost
            try:
                self._emitter.emit_nowait(self._execution_id, "usage", payload)
            except Exception:
                pass

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
