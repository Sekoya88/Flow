from __future__ import annotations

import json
import re
from datetime import UTC, datetime
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
    now = datetime.now(tz=UTC)
    if last_reinforced_at.tzinfo is None:
        last_reinforced_at = last_reinforced_at.replace(tzinfo=UTC)
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


# Curated list of common skills/tools to regex-match in résumé text. Each entry is
# (regex_pattern, canonical_name). Case-insensitive word-boundary matching.
_REGEX_FACETS: list[tuple[str, str]] = [
    # Languages
    (r"\bpython\b", "Python"),
    (r"\btypescript\b|\btype\s?script\b", "TypeScript"),
    (r"\bjavascript\b|\bjs\b", "JavaScript"),
    (r"\bgolang\b|\bgo\b(?!ogle)", "Go"),
    (r"\brust\b", "Rust"),
    (r"\bjava\b(?!script)", "Java"),
    (r"\bkotlin\b", "Kotlin"),
    (r"\bswift\b", "Swift"),
    (r"\bc\+\+\b|\bcpp\b", "C++"),
    (r"\bc#\b|\bcsharp\b", "C#"),
    (r"\bruby\b", "Ruby"),
    (r"\bphp\b", "PHP"),
    (r"\bscala\b", "Scala"),
    (r"\belixir\b", "Elixir"),
    (r"\bsql\b", "SQL"),
    # Frontend
    (r"\breact\b", "React"),
    (r"\bnext\.?js\b", "Next.js"),
    (r"\bvue\b", "Vue"),
    (r"\bangular\b", "Angular"),
    (r"\bsvelte\b", "Svelte"),
    (r"\btailwind\b", "Tailwind"),
    # Backend frameworks
    (r"\bdjango\b", "Django"),
    (r"\bfastapi\b", "FastAPI"),
    (r"\bflask\b", "Flask"),
    (r"\bspring\s?boot\b|\bspring\b", "Spring Boot"),
    (r"\bnode\.?js\b|\bnodejs\b", "Node.js"),
    (r"\bexpress\b", "Express"),
    (r"\b\.net\b|\bdotnet\b", ".NET"),
    # Cloud / Infra
    (r"\baws\b|\bamazon\s+web\s+services\b", "AWS"),
    (r"\bgcp\b|\bgoogle\s+cloud\b", "GCP"),
    (r"\bazure\b", "Azure"),
    (r"\bdocker\b", "Docker"),
    (r"\bkubernetes\b|\bk8s\b", "Kubernetes"),
    (r"\bterraform\b", "Terraform"),
    (r"\bansible\b", "Ansible"),
    # Data
    (r"\bpostgres(?:ql)?\b", "PostgreSQL"),
    (r"\bmysql\b", "MySQL"),
    (r"\bmongo(?:db)?\b", "MongoDB"),
    (r"\bredis\b", "Redis"),
    (r"\belastic(?:search)?\b", "Elasticsearch"),
    (r"\bkafka\b", "Kafka"),
    # ML
    (r"\bpytorch\b", "PyTorch"),
    (r"\btensorflow\b", "TensorFlow"),
    (r"\bpandas\b", "Pandas"),
    (r"\bnumpy\b", "NumPy"),
    (r"\bscikit[-\s]?learn\b|\bsklearn\b", "scikit-learn"),
    (r"\blangchain\b", "LangChain"),
    (r"\blanggraph\b", "LangGraph"),
    # Tools
    (r"\bgit\b", "Git"),
    (r"\bgithub\b", "GitHub"),
    (r"\bgitlab\b", "GitLab"),
]


def regex_extract_facets(text: str) -> list[dict[str, str]]:
    """Deterministic facet extraction from résumé text. No LLM required.

    Scans for canonical tool/language names. Each unique hit becomes a single
    ``{"class": "tooling", "value": "<name>"}`` entry. Order is the order they
    were declared in ``_REGEX_FACETS``.
    """
    if not text:
        return []
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for pattern, canonical in _REGEX_FACETS:
        if canonical in seen:
            continue
        if re.search(pattern, text, flags=re.IGNORECASE):
            seen.add(canonical)
            found.append({"class": "tooling", "value": canonical})
    return found


def merge_facets(
    primary: list[dict[str, str]],
    secondary: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Merge two preference lists, deduping on (class, value) — primary wins."""
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for item in primary + secondary:
        cls = item.get("class", "")
        val = (item.get("value") or "").strip()
        if not cls or not val:
            continue
        key = (cls, val.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({"class": cls, "value": val})
    return out


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
