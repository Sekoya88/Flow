"""Deep Agents harness for multi-shard CV → preference extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import ToolMessage
from pydantic import ValidationError

from flow.config import Settings
from flow.domain.preferences.cv_schemas import (
    NarrativeCvShard,
    ToolingCvShard,
    VetoChannelCvShard,
)

_SKILLS_ROOT = Path(__file__).resolve().parent / "skills"

_COORDINATOR_PROMPT = """You coordinate résumé analysis for a user profile system.

You MUST use the `task` tool exactly three times on the user's résumé (same text each time):
1. `subagent_type="tooling_extractor"` — pass the full résumé in `description`.
2. `subagent_type="narrative_facets"` — pass the full résumé in `description`.
3. `subagent_type="veto_channel"` — pass the full résumé in `description`.

Do not invent employers or credentials. After the three task calls, reply with a single line: DONE."""

_TOOLING_SUB_PROMPT = (
    "You receive résumé text in the user message. Extract tooling only: "
    "languages, frameworks, clouds, data stores, and well-known platforms. "
    "Return structured output only via your configured response schema."
)

_NARRATIVE_SUB_PROMPT = (
    "You receive résumé text in the user message. Extract domains (industry/role area), "
    "goals (what they are building or learning), and style_hints (communication preferences). "
    "Return structured output only via your configured response schema."
)

_VETO_SUB_PROMPT = (
    "You receive résumé text in the user message. Infer explicit dislikes as vetoes "
    "and preferred presentation channels for technical content when clearly implied; "
    "otherwise leave lists empty. Return structured output only via your configured response schema."
)


def build_cv_profile_chat_model(settings: Settings) -> BaseChatModel | None:
    """Instantiated chat model with FLOW_* API keys (avoids init_chat_model env mismatch)."""
    if settings.anthropic_api_key:
        try:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model="claude-haiku-4-5-20251001",
                api_key=settings.anthropic_api_key,
            )
        except Exception:
            pass
    if settings.openai_api_key:
        try:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model="gpt-5.4-mini",
                api_key=settings.openai_api_key,
            )
        except Exception:
            pass
    return None


def build_cv_profile_agent(model: str | BaseChatModel) -> Any:
    """Compiled LangGraph agent with three structured-output subagents."""
    subagents: list[dict[str, Any]] = [
        {
            "name": "tooling_extractor",
            "description": "Extracts programming languages, frameworks, and infra tools from résumé text.",
            "system_prompt": _TOOLING_SUB_PROMPT,
            "response_format": ToolingCvShard,
        },
        {
            "name": "narrative_facets",
            "description": "Extracts domain, goals, and style hints from résumé text.",
            "system_prompt": _NARRATIVE_SUB_PROMPT,
            "response_format": NarrativeCvShard,
        },
        {
            "name": "veto_channel",
            "description": "Extracts vetoes and channel preferences when clearly supported by the résumé.",
            "system_prompt": _VETO_SUB_PROMPT,
            "response_format": VetoChannelCvShard,
        },
    ]
    skills_path = str(_SKILLS_ROOT) if _SKILLS_ROOT.is_dir() else None
    kw: dict[str, Any] = {
        "model": model,
        "system_prompt": _COORDINATOR_PROMPT,
        "subagents": subagents,
    }
    if skills_path:
        kw["skills"] = [skills_path]
    return create_deep_agent(**kw)


def _parse_shard_dict(data: dict[str, Any]) -> tuple[str, Any] | None:
    if not isinstance(data, dict):
        return None
    keys = set(data)
    if "items" in keys and isinstance(data.get("items"), list):
        try:
            return ("tooling", ToolingCvShard.model_validate(data))
        except ValidationError:
            return None
    if keys & {"domains", "goals", "style_hints"}:
        try:
            return ("narrative", NarrativeCvShard.model_validate(data))
        except ValidationError:
            return None
    if "vetoes" in keys or "channels" in keys:
        try:
            return ("veto_ch", VetoChannelCvShard.model_validate(data))
        except ValidationError:
            return None
    return None


def parse_subagent_tool_payloads(
    messages: list[Any],
) -> tuple[ToolingCvShard | None, NarrativeCvShard | None, VetoChannelCvShard | None]:
    """Recover structured shards from `task` ToolMessage JSON bodies."""
    tooling: ToolingCvShard | None = None
    narrative: NarrativeCvShard | None = None
    veto_ch: VetoChannelCvShard | None = None

    for m in messages:
        if not isinstance(m, ToolMessage):
            continue
        if m.name and m.name != "task":
            continue
        if not m.content or not isinstance(m.content, str):
            continue
        try:
            data = json.loads(m.content)
        except (json.JSONDecodeError, TypeError):
            continue
        parsed = _parse_shard_dict(data)
        if not parsed:
            continue
        kind, obj = parsed
        if kind == "tooling":
            tooling = obj
        elif kind == "narrative":
            narrative = obj
        elif kind == "veto_ch":
            veto_ch = obj

    return tooling, narrative, veto_ch
