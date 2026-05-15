"""Application service: CV text → typed preference rows (Deep Agent + regex backstop)."""

from __future__ import annotations

import io
from typing import Any

import structlog
from langchain_core.messages import HumanMessage

from flow.application.preference_service import merge_facets, regex_extract_facets
from flow.config import Settings
from flow.domain.preferences.cv_mapping import shards_to_preference_rows
from flow.infrastructure.llm.cv_profile_deep_agent import (
    build_cv_profile_agent,
    build_cv_profile_chat_model,
    parse_subagent_tool_payloads,
)

log = structlog.get_logger(__name__)

_VALID = frozenset({"style", "tooling", "veto", "goal", "domain", "channel"})
_MAX_RESUME_CHARS = 14_000


def extract_cv_text_from_bytes(raw: bytes, *, is_pdf: bool) -> str:
    """Plain text from PDF or DOCX bytes."""
    if is_pdf:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    import docx

    doc = docx.Document(io.BytesIO(raw))
    return "\n".join(p.text for p in doc.paragraphs)


def _filter_valid(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in rows if r.get("class") in _VALID and (r.get("value") or "").strip()]


async def run_cv_preference_extraction(
    settings: Settings,
    resume_text: str,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Run Deep Agent (when configured) plus regex merge; returns rows for upsert."""
    trimmed = resume_text[:_MAX_RESUME_CHARS]
    regex_rows = regex_extract_facets(resume_text)
    meta: dict[str, Any] = {"regex_count": len(regex_rows), "deep_agent": False}

    chat = build_cv_profile_chat_model(settings)
    if chat is None:
        merged = merge_facets([], regex_rows)
        return _filter_valid(merged), meta

    meta["deep_agent"] = True
    meta["model"] = getattr(chat, "model_name", None) or type(chat).__name__
    agent = build_cv_profile_agent(chat)
    human = HumanMessage(
        content=(
            "Extract profile facets from this résumé. Follow your system instructions "
            "exactly (three `task` calls).\n\n<RESUME>\n"
            f"{trimmed}\n</RESUME>"
        )
    )
    try:
        result = await agent.ainvoke({"messages": [human]})
    except Exception as exc:
        log.warning("cv.deep_agent.invoke_failed", error=str(exc))
        merged = merge_facets([], regex_rows)
        meta["error"] = str(exc)
        return _filter_valid(merged), meta

    messages = result.get("messages") or []
    tooling, narrative, veto_ch = parse_subagent_tool_payloads(messages)
    ai_rows = shards_to_preference_rows(tooling, narrative, veto_ch)
    meta["shard_counts"] = {
        "tooling_items": len(tooling.items) if tooling else 0,
        "narrative_domains": len(narrative.domains) if narrative else 0,
        "veto": len(veto_ch.vetoes) if veto_ch else 0,
    }
    merged = merge_facets(ai_rows, regex_rows)
    return _filter_valid(merged), meta
