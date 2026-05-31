from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from flow.infrastructure.llm.middleware.base import AgentMiddleware, HarnessRuntime
from flow.infrastructure.observability.logging import get_logger

_default_logger = get_logger(__name__)


class FlowObservabilityMiddleware(AgentMiddleware):
    """Log latency, token counts, and tool outcomes on every LLM/tool call."""

    def __init__(self, logger: Any = None) -> None:
        self._log = logger or _default_logger

    async def wrap_model_call(self, invoke: Callable, messages: list) -> Any:
        t0 = time.monotonic()
        response = await invoke(messages)
        latency_ms = int((time.monotonic() - t0) * 1000)

        input_tokens = 0
        output_tokens = 0
        try:
            gens = getattr(response, "generations", [])
            if gens:
                msg = gens[0][0].message if gens[0] else None
                content = getattr(msg, "content", "") if msg else ""
                output_tokens = len(content.split())
                usage = getattr(msg, "usage_metadata", None) or {}
                if usage:
                    input_tokens = usage.get("input_tokens", input_tokens)
                    output_tokens = usage.get("output_tokens", output_tokens)
        except Exception:
            pass

        self._log.info(
            "model.end",
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return response

    async def wrap_tool_call(self, invoke: Callable, args: dict) -> Any:
        t0 = time.monotonic()
        try:
            result = await invoke(args)
            self._log.info(
                "tool.end",
                duration_ms=int((time.monotonic() - t0) * 1000),
                status="ok",
            )
            return result
        except Exception as exc:
            self._log.error(
                "tool.error",
                error=str(exc),
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
            raise

    async def on_tool_result(self, tool_name: str, output: str, runtime: HarnessRuntime) -> None:
        self._log.info(
            "tool.result",
            tool=tool_name,
            output_chars=len(output),
            execution_id=str(runtime.execution_id),
        )
