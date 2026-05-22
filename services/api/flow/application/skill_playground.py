"""Single-skill, single-prompt streaming playground.

Powers the Skills Hub's "test against a prompt" surface. Deliberately bypasses
LangGraph, the checkpointer, and the executions table — test runs are isolated
and don't pollute history, memory, or KG ingestion.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from flow.application.skill_parser import parse_skill_md


def _build_skill_llm(settings: Any) -> Any | None:
    """Anthropic Haiku → OpenAI gpt-5.4-mini → None. Mirrors persona_service."""
    if getattr(settings, "anthropic_api_key", None):
        try:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model="claude-haiku-4-5-20251001",
                api_key=settings.anthropic_api_key,
                streaming=True,
            )
        except Exception:
            pass
    if getattr(settings, "openai_api_key", None):
        try:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model="gpt-5.4-mini",
                api_key=settings.openai_api_key,
                streaming=True,
            )
        except Exception:
            pass
    return None


def _format_skill_system_prompt(content_md: str) -> str:
    """Compose the SystemMessage body. Mirrors nodes.py:235-240 progressive disclosure."""
    parsed = parse_skill_md(content_md)
    tools_line = ", ".join(parsed.allowed_tools) if parsed.allowed_tools else "any"
    return (
        f"You are testing the skill [{parsed.name} v{parsed.version}].\n"
        f"Description: {parsed.description}\n"
        f"Allowed tools: {tools_line}\n\n"
        f"{parsed.body_md}"
    )


async def run_skill_test(
    settings: Any,
    skill_content_md: str,
    prompt: str,
    llm: Any | None = None,
) -> AsyncIterator[str]:
    """Yield token strings as the LLM streams its response.

    `llm` arg is for tests — production callers pass settings only.
    """
    if llm is None:
        llm = _build_skill_llm(settings)
    if llm is None:
        yield "(no LLM provider configured — set ANTHROPIC_API_KEY or OPENAI_API_KEY)"
        return

    system = _format_skill_system_prompt(skill_content_md)
    messages = [SystemMessage(content=system), HumanMessage(content=prompt)]

    try:
        async for chunk in llm.astream(messages):
            text = getattr(chunk, "content", "") or ""
            if isinstance(text, list):
                # Anthropic streaming sometimes emits structured blocks
                text = "".join((b.get("text", "") if isinstance(b, dict) else str(b)) for b in text)
            text = str(text)
            if text:
                yield text
    except Exception as exc:
        yield f"\n\n[stream error: {exc}]"
