"""Vibe-create and vibe-modify skills via natural language prompting.

Streams the generated SKILL.md content token by token, then returns the
full content for the caller to persist as an inactive candidate version.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

_SKILL_TEMPLATE = """\
---
name: skill-name
description: Use this skill when the user asks about X
version: "1.0"
category: General
allowed-tools: retrieve
triggers:
  - "example trigger phrase"
metadata:
  author: flow
---

# Skill Name

<context>
Brief background the agent needs to apply this skill correctly.
</context>

<instructions>
1. Step one
2. Step two
3. Step three
</instructions>

<output_format>
Describe the expected response structure.
</output_format>

<examples>
**Input:** Example user message
**Output:** Expected agent response
</examples>
"""

_SYSTEM_CREATE = f"""\
You are a skill author for an agentic AI assistant. Your task is to write a SKILL.md file \
based on the user's description. Output ONLY the raw SKILL.md content — no explanations, \
no markdown fences, no preamble.

Follow this exact template format:
{_SKILL_TEMPLATE}

Rules:
- name: lowercase-kebab-case, descriptive
- description: start with "Use this skill when..." — max 200 chars
- category: one of General, Research, Code, Communication, Analysis, Memory, Planning
- triggers: 2-4 short phrases that a user might say to invoke this skill
- Use <context>, <instructions>, <output_format>, <examples> XML sections in the body
- <instructions> must have numbered steps
- <examples> must have at least one Input/Output pair
"""

_SYSTEM_MODIFY = """\
You are a skill author for an agentic AI assistant. You will be given an existing SKILL.md \
and a modification request. Output ONLY the complete updated SKILL.md — no explanations, \
no markdown fences, no preamble. Preserve the overall structure and format. \
Increment the version field by 0.1.
"""


def _build_vibe_llm(settings: Any) -> Any | None:
    """Use Sonnet for creation (higher quality than playground's Haiku)."""
    if getattr(settings, "anthropic_api_key", None):
        try:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model="claude-sonnet-4-6",
                api_key=settings.anthropic_api_key,
                streaming=True,
                max_tokens=4096,
            )
        except Exception:
            pass
    if getattr(settings, "openai_api_key", None):
        try:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model="gpt-4o",
                api_key=settings.openai_api_key,
                streaming=True,
            )
        except Exception:
            pass
    return None


async def vibe_create_skill(
    settings: Any,
    prompt: str,
    category: str = "General",
) -> AsyncIterator[str]:
    """Yield SKILL.md tokens from a natural-language description."""
    llm = _build_vibe_llm(settings)
    if llm is None:
        yield "(no LLM provider configured — set ANTHROPIC_API_KEY or OPENAI_API_KEY)"
        return

    user_msg = f"Category: {category}\n\nDescription: {prompt}"
    messages = [SystemMessage(content=_SYSTEM_CREATE), HumanMessage(content=user_msg)]

    try:
        async for chunk in llm.astream(messages):
            text = getattr(chunk, "content", "") or ""
            if isinstance(text, list):
                text = "".join((b.get("text", "") if isinstance(b, dict) else str(b)) for b in text)
            text = str(text)
            if text:
                yield text
    except Exception as exc:
        yield f"\n\n[stream error: {exc}]"


async def vibe_modify_skill(
    settings: Any,
    current_content_md: str,
    prompt: str,
) -> AsyncIterator[str]:
    """Yield modified SKILL.md tokens given an existing skill and a change request."""
    llm = _build_vibe_llm(settings)
    if llm is None:
        yield "(no LLM provider configured — set ANTHROPIC_API_KEY or OPENAI_API_KEY)"
        return

    user_msg = f"Existing SKILL.md:\n\n{current_content_md}\n\nModification request: {prompt}"
    messages = [SystemMessage(content=_SYSTEM_MODIFY), HumanMessage(content=user_msg)]

    try:
        async for chunk in llm.astream(messages):
            text = getattr(chunk, "content", "") or ""
            if isinstance(text, list):
                text = "".join((b.get("text", "") if isinstance(b, dict) else str(b)) for b in text)
            text = str(text)
            if text:
                yield text
    except Exception as exc:
        yield f"\n\n[stream error: {exc}]"
