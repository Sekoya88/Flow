from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from flow.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class HarnessRuntime:
    workspace_id: UUID
    agent_id: UUID
    user_id: UUID
    execution_id: UUID
    thread_id: str


class AgentMiddleware:
    """Base class for Flow middleware. Override any subset of hooks."""

    async def before_agent(self, state: dict, runtime: HarnessRuntime) -> dict:
        """Modify initial state before graph.astream() is called. Return modified state."""
        return state

    async def after_agent(self, state: dict, runtime: HarnessRuntime) -> None:
        """Side effects after the graph finishes. Failures are logged and swallowed."""
        pass

    async def before_model(self, messages: list, runtime: HarnessRuntime) -> dict | None:
        """Called before each LLM invocation. Return {"jump_to": "end"} to stop early."""
        return None

    async def wrap_model_call(self, invoke: Callable, messages: list) -> Any:
        """Wrap an LLM invocation. Call await invoke(messages) to proceed."""
        return await invoke(messages)

    async def wrap_tool_call(self, invoke: Callable, args: dict) -> Any:
        """Wrap a tool invocation. Call await invoke(args) to proceed."""
        return await invoke(args)


class FlowMiddlewareHarness:
    """Wraps a compiled LangGraph, running middleware before/after execution.

    Presents the same astream / aget_state interface as a compiled graph so
    execution_runner.py needs no changes.
    """

    def __init__(
        self,
        graph: Any,
        middleware: list[AgentMiddleware],
        runtime: HarnessRuntime,
    ) -> None:
        self._graph = graph
        self._middleware = middleware
        self._runtime = runtime

    async def astream(
        self, input_state: dict, config: dict, **kwargs
    ) -> AsyncGenerator:
        # before_agent: each middleware may augment initial state
        state = input_state
        for m in self._middleware:
            state = await m.before_agent(state, self._runtime)

        # Stream graph, collecting node updates for after_agent
        final_chunks: dict = {}
        try:
            async for item in self._graph.astream(state, config, **kwargs):
                # Support both multi-mode (mode, chunk) and single-mode chunk
                if isinstance(item, tuple) and len(item) == 2:
                    mode, chunk = item
                    if mode == "updates" and isinstance(chunk, dict):
                        final_chunks.update(chunk)
                yield item
        finally:
            # Merge node partials into a flat final-state dict for after_agent
            merged: dict = {}
            for node_partial in final_chunks.values():
                if isinstance(node_partial, dict):
                    merged.update(node_partial)
            for m in self._middleware:
                try:
                    await m.after_agent(merged, self._runtime)
                except Exception as exc:
                    logger.error(
                        "middleware.after_agent.error",
                        middleware=type(m).__name__,
                        error=str(exc),
                    )

    async def aget_state(self, config: dict) -> Any:
        return await self._graph.aget_state(config)

    def get_state(self, config: dict) -> Any:
        return self._graph.get_state(config)
