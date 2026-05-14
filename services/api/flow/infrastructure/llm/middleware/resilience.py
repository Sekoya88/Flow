from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from flow.infrastructure.llm.middleware.base import AgentMiddleware, HarnessRuntime
from flow.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


def _retryable_exceptions():
    excs = []
    try:
        from openai import RateLimitError, APIStatusError, APITimeoutError
        excs += [RateLimitError, APIStatusError, APITimeoutError]
    except ImportError:
        pass
    try:
        from anthropic import RateLimitError as AnthRLE, APIStatusError as AnthASE
        excs += [AnthRLE, AnthASE]
    except ImportError:
        pass
    return tuple(excs) if excs else (OSError,)


class FlowResilienceMiddleware(AgentMiddleware):
    """Retry transient LLM/tool errors with exponential backoff."""

    def __init__(
        self,
        model_retry: int = 3,
        tool_retry: int = 2,
        min_wait: float = 1.0,
        max_wait: float = 10.0,
        backoff_factor: float = 1.5,
    ) -> None:
        self._model_retry = model_retry
        self._tool_retry = tool_retry
        self._min_wait = min_wait
        self._max_wait = max_wait
        self._backoff_factor = backoff_factor

    def patch_llm(self, llm: Any) -> None:
        """Wrap llm._agenerate with tenacity retry in-place."""
        if not hasattr(llm, "_agenerate"):
            return
        retryable = _retryable_exceptions()
        original = llm._agenerate

        @retry(
            stop=stop_after_attempt(self._model_retry),
            wait=wait_exponential(
                multiplier=self._backoff_factor,
                min=self._min_wait,
                max=self._max_wait,
            ),
            retry=retry_if_exception_type(retryable),
            reraise=True,
        )
        async def _retried(*args, **kwargs):
            return await original(*args, **kwargs)

        llm._agenerate = _retried

    async def wrap_tool_call(self, invoke: Callable, args: dict) -> Any:
        from tenacity import RetryError

        # Tools may also fail with network/OS errors not covered by provider SDKs
        retryable = _retryable_exceptions() + (OSError, ConnectionError, TimeoutError)

        @retry(
            stop=stop_after_attempt(self._tool_retry),
            wait=wait_exponential(
                multiplier=self._backoff_factor,
                min=self._min_wait,
                max=self._max_wait,
            ),
            retry=retry_if_exception_type(retryable),
            reraise=True,  # raises original exception after exhaustion
        )
        async def _retried():
            return await invoke(args)

        try:
            return await _retried()
        except retryable as exc:
            # Only swallow retryable exhaustion — programming errors propagate normally
            logger.error("tool.failed", error=str(exc))
            return None
