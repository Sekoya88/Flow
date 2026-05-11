"""Factory for building LangGraph prebuilt react agents with provider-aware LLM selection."""
from __future__ import annotations

from typing import Any


def build_agent(
    *,
    provider: str,
    model: str,
    api_key: str | None,
    tools: list[Any] | None = None,
    system_prompt: str | None = None,
    checkpointer: Any | None = None,
    store: Any | None = None,
    temperature: float = 0.2,
):
    """Return a compiled LangGraph react-agent graph.

    Selects the LLM based on *provider*. Returns None if the required API key is absent.
    The returned graph has the same streaming interface as manually compiled graphs.
    """
    from flow.infrastructure.llm.providers import get_chat_model

    llm = get_chat_model(
        {"provider": provider, "model": model, "temperature": temperature},
        {"openai": api_key if provider == "openai" else None,
         "anthropic": api_key if provider == "anthropic" else None},
    )
    if llm is None:
        return None

    from langgraph.prebuilt import create_react_agent

    kwargs: dict[str, Any] = {
        "model": llm,
        "tools": tools or [],
    }
    if system_prompt:
        kwargs["prompt"] = system_prompt
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer
    if store is not None:
        kwargs["store"] = store

    return create_react_agent(**kwargs)
