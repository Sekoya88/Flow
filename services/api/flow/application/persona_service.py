"""SOUL.md persona — synthesize a single durable identity block per user.

The persona is injected as system-prompt slot #1 by FlowPersonaMiddleware.
We synthesize it from the user's typed preferences (style/tooling/veto/goal/
domain/channel) plus optional CV-extracted text. LLM is preferred but the
function has a deterministic fallback so it works even with no API key.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage

_PERSONA_PROMPT = """\
You are writing a SOUL.md — a durable identity sheet for an AI assistant.
It will be injected as the FIRST block of the assistant's system prompt for
every conversation with this user. Keep it personal, calm, and stable across
contexts. Target ~250 words maximum.

Use this structure (markdown headings exactly as below):

# Identity
One paragraph: who is this user, what's their stance, what they care about.

## Voice & style
Bullets — how should the assistant speak with them (tone, formatting, depth).

## What to avoid
Bullets — patterns, tools, or styles they explicitly do not want.

## Current focus
Bullets — what they're working on or learning right now.

## Technical posture
Bullets — preferred stack, conventions, level of detail.

Constraints:
- DO NOT invent facts. Use only what's in the data below.
- If a section has no data, write a single bullet "(unspecified)" — never fabricate.
- Output ONLY the markdown. No preamble.

Data:
preferences (typed facets):
{facets_json}

resume text (truncated):
{cv_text}
"""


def _format_template(facets: list[dict[str, str]], cv_text: str | None) -> str:
    """Deterministic fallback when no LLM is available."""
    by_class: dict[str, list[str]] = {}
    for f in facets:
        by_class.setdefault(f.get("class", ""), []).append(f.get("value", ""))

    def joined(cls: str) -> str:
        items = [v for v in by_class.get(cls, []) if v]
        return ", ".join(items) if items else "(unspecified)"

    domain = joined("domain")
    style = joined("style")
    tooling = joined("tooling")
    veto = joined("veto")
    goal = joined("goal")
    channel = joined("channel")

    return f"""# Identity
You are working with a {domain} practitioner.

## Voice & style
- Communication style: {style}
- Output channel preferences: {channel}

## What to avoid
- {veto}

## Current focus
- {goal}

## Technical posture
- Preferred tooling: {tooling}
"""


async def synthesize_persona(
    llm: Any | None,
    facets: list[dict[str, str]],
    cv_text: str | None,
) -> str:
    """Build a SOUL.md from the user's preferences (+ optional CV text).

    Returns the markdown content. Empty list of facets + no CV → returns a
    minimal template (still useful as a starting point the user can edit).
    """
    if llm is None or not facets:
        return _format_template(facets, cv_text)
    truncated_cv = (cv_text or "")[:3000]
    prompt = _PERSONA_PROMPT.format(
        facets_json=json.dumps(facets, ensure_ascii=False, indent=2),
        cv_text=truncated_cv or "(no resume on file)",
    )
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        text = getattr(response, "content", "") or ""
        if isinstance(text, list):
            # Anthropic content blocks
            text = "\n".join(
                str(b.get("text", "")) if isinstance(b, dict) else str(b)
                for b in text
            )
        text = str(text).strip()
        return text or _format_template(facets, cv_text)
    except Exception:
        return _format_template(facets, cv_text)


def _build_persona_llm(settings: Any) -> Any | None:
    """Prefer Anthropic Haiku, fall back to OpenAI gpt-4o-mini, else None."""
    if getattr(settings, "anthropic_api_key", None):
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model="claude-haiku-4-5-20251001",
                api_key=settings.anthropic_api_key,
            )
        except Exception:
            pass
    if getattr(settings, "openai_api_key", None):
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model="gpt-4o-mini",
                api_key=settings.openai_api_key,
            )
        except Exception:
            pass
    return None


_QUESTIONNAIRE_PROMPT = """\
You are writing a SOUL.md — a durable identity sheet for an AI assistant.
It will be injected as the FIRST block of the assistant's system prompt for
every conversation with this user. Keep it personal, warm, and stable across
contexts. Target ~200 words maximum.

Use this structure (markdown headings exactly as below):

# Identity
One paragraph: who is this user, what they do, what they care about.

## Voice & style
Bullets — how should the assistant speak with them (tone, depth, format).

## What to avoid
Bullets — patterns or styles they don't want.

## Current focus
Bullets — what they're working on right now.

## Technical posture
Bullets — preferred stack or domain conventions, if mentioned.

Constraints:
- DO NOT invent facts. Use only what's in the answers below.
- If a section has no data, write a single bullet "(unspecified)".
- Output ONLY the markdown. No preamble.

User's questionnaire answers:
{qa_text}
"""


async def synthesize_from_questionnaire(
    llm: Any | None,
    answers: list[dict[str, str]],
) -> str:
    """Build a SOUL.md from explicit questionnaire Q&A pairs."""
    qa_text = "\n".join(
        f"Q: {a.get('question', '').strip()}\nA: {a.get('answer', '').strip()}"
        for a in answers
        if a.get("answer", "").strip()
    )
    if not qa_text:
        return _format_template([], None)
    if llm is None:
        lines = ["# Identity", ""]
        for a in answers:
            q = a.get("question", "").strip()
            v = a.get("answer", "").strip()
            if v:
                lines.append(f"- **{q}**: {v}")
        lines += ["", "## Voice & style", "- (unspecified)", "", "## What to avoid", "- (unspecified)", "", "## Current focus", "- (unspecified)", "", "## Technical posture", "- (unspecified)"]
        return "\n".join(lines)
    prompt = _QUESTIONNAIRE_PROMPT.format(qa_text=qa_text)
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        text = getattr(response, "content", "") or ""
        if isinstance(text, list):
            text = "\n".join(str(b.get("text", "")) if isinstance(b, dict) else str(b) for b in text)
        text = str(text).strip()
        return text or _format_template([], None)
    except Exception:
        return _format_template([], None)


async def regenerate_persona(
    pool: Any,
    workspace_id: UUID,
    user_id: UUID,
    settings: Any,
) -> dict[str, Any]:
    """Pull facets → synthesize SOUL.md → upsert user_personas → return row.

    Bumps version on each regenerate. Caller passes a real asyncpg.Pool.
    """
    facet_rows = await pool.fetch(
        """
        SELECT class, value, status, score
        FROM user_preferences
        WHERE workspace_id = $1 AND user_id = $2 AND status IN ('active', 'provisional')
        ORDER BY score DESC
        LIMIT 80
        """,
        workspace_id,
        user_id,
    )
    facets = [
        {"class": r["class"], "value": r["value"]}
        for r in facet_rows
    ]
    llm = _build_persona_llm(settings)
    content = await synthesize_persona(llm, facets, cv_text=None)

    derived = {
        "preferences": len(facets),
        "cv": False,  # we don't keep the raw CV text — CV-extracted facts live in user_preferences
        "manual": False,
        "llm": llm is not None,
    }

    row = await pool.fetchrow(
        """
        INSERT INTO user_personas (workspace_id, user_id, content_md, version, derived_from)
        VALUES ($1, $2, $3, 1, $4::jsonb)
        ON CONFLICT (workspace_id, user_id) DO UPDATE
        SET content_md = EXCLUDED.content_md,
            version = user_personas.version + 1,
            derived_from = EXCLUDED.derived_from,
            updated_at = now()
        RETURNING id, workspace_id, user_id, content_md, version, derived_from, created_at, updated_at
        """,
        workspace_id,
        user_id,
        content,
        json.dumps(derived),
    )
    assert row is not None
    return dict(row)
