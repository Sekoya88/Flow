from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage

_VALID_CLASSES = {"style", "tooling", "veto", "goal", "domain", "channel"}

_EXTRACT_PROMPT = """\
Given this conversation, extract signals about the user's stable preferences.
Return JSON array: [{{"class": "<class>", "value": "<short declarative phrase>"}}]
Classes: style, tooling, veto, goal, domain, channel
Rules:
- Only extract clear, stable signals (not one-off requests)
- value must be a short declarative phrase (max 10 words)
- Omit anything ambiguous or run-specific
- Return [] if no clear preferences found

Conversation:
{conversation}"""

_CV_PROMPT = """\
You are reading a professional résumé. Extract stable user preferences for an AI assistant.
Return JSON: [{{"class": "<class>", "value": "<short declarative phrase>"}}]
Classes: style, tooling, veto, goal, domain, channel
Focus on:
- Programming languages and frameworks mentioned → tooling
- Industry / domain / sector → domain
- Seniority and communication preferences implied by role titles → style
- Career goals or current focus areas → goal
Return 10-25 items. Short declarative phrases only (max 10 words each).

Résumé:
{text}"""


def effective_score(
    score: float,
    last_reinforced_at: datetime,
    decay_half_life_days: int,
    pinned: bool = False,
) -> float:
    if pinned:
        return score
    now = datetime.now(tz=timezone.utc)
    if last_reinforced_at.tzinfo is None:
        last_reinforced_at = last_reinforced_at.replace(tzinfo=timezone.utc)
    days_since = (now - last_reinforced_at).total_seconds() / 86400
    return score * (0.5 ** (days_since / decay_half_life_days))


def auto_graduate(row: dict[str, Any]) -> str | None:
    """Return next status if graduation threshold met, else None."""
    eff = effective_score(
        row["score"],
        row["last_reinforced_at"],
        row["decay_half_life_days"],
        row.get("pinned", False),
    )
    if row["status"] == "candidate" and eff >= 0.7:
        return "provisional"
    if row["status"] == "provisional" and eff >= 0.9:
        return "active"
    return None


def _parse_prefs(content: str) -> list[dict[str, str]]:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [
        {"class": item["class"], "value": item["value"]}
        for item in data
        if isinstance(item, dict)
        and item.get("class") in _VALID_CLASSES
        and item.get("value")
        and isinstance(item["value"], str)
    ]


async def extract_preferences(llm: Any, conversation: str) -> list[dict[str, str]]:
    prompt = _EXTRACT_PROMPT.format(conversation=conversation[:4000])
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return _parse_prefs(response.content)
    except Exception:
        return []


async def extract_preferences_from_cv(llm: Any, text: str) -> list[dict[str, str]]:
    truncated = text[:8000]
    prompt = _CV_PROMPT.format(text=truncated)
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        return _parse_prefs(response.content)
    except Exception:
        return []


def process_onboarding_answers(
    answers: list[dict[str, str]],
) -> list[dict[str, str]]:
    result = []
    for a in answers:
        cls = a.get("class", "")
        val = (a.get("value") or "").strip()
        if cls in _VALID_CLASSES and val:
            result.append({"class": cls, "value": val, "status": "active"})
    return result
