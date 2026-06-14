"""Application service: CV text → typed preference rows (Deep Agent + regex backstop)."""

from __future__ import annotations

import io
import json
from collections.abc import AsyncIterator
from typing import Any

import structlog
from langchain_core.messages import HumanMessage, ToolMessage

from flow.application.preference_service import merge_facets, regex_extract_facets
from flow.config import Settings
from flow.domain.preferences.cv_mapping import shards_to_preference_rows
from flow.infrastructure.llm.cv_profile_deep_agent import (
    _parse_shard_dict,
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


_SHARD_LABELS = {"tooling": "tooling", "narrative": "narrative", "veto_ch": "veto/channel"}


async def run_cv_preference_extraction_streamed(
    settings: Settings,
    resume_text: str,
) -> AsyncIterator[dict[str, Any]]:
    """Streaming variant: yields progress events as each Deep Agent shard completes.

    Event kinds: `cv.start`, `cv.shard` (one per completed extractor subagent),
    `cv.done` (carries the final `rows` + `meta`). Falls back to regex-only on any
    Deep Agent failure, like the non-streaming path.
    """
    trimmed = resume_text[:_MAX_RESUME_CHARS]
    regex_rows = regex_extract_facets(resume_text)
    meta: dict[str, Any] = {"regex_count": len(regex_rows), "deep_agent": False}

    chat = build_cv_profile_chat_model(settings)
    if chat is None:
        merged = merge_facets([], regex_rows)
        yield {"kind": "cv.done", "rows": _filter_valid(merged), "meta": meta}
        return

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
    yield {"kind": "cv.start", "model": meta["model"], "shards_total": 3}

    all_messages: list[Any] = []
    shards_seen = 0
    try:
        async for chunk in agent.astream({"messages": [human]}, stream_mode="updates"):
            for _node, partial in (chunk or {}).items():
                msgs = (partial or {}).get("messages") if isinstance(partial, dict) else None
                for m in msgs or []:
                    all_messages.append(m)
                    if not isinstance(m, ToolMessage) or (m.name and m.name != "task"):
                        continue
                    if not isinstance(m.content, str) or not m.content:
                        continue
                    try:
                        parsed = _parse_shard_dict(json.loads(m.content))
                    except (json.JSONDecodeError, TypeError):
                        parsed = None
                    if parsed:
                        shards_seen += 1
                        yield {
                            "kind": "cv.shard",
                            "shard": _SHARD_LABELS.get(parsed[0], parsed[0]),
                            "shards_done": shards_seen,
                            "shards_total": 3,
                        }
    except Exception as exc:
        log.warning("cv.deep_agent.stream_failed", error=str(exc))
        meta["error"] = str(exc)
        merged = merge_facets([], regex_rows)
        yield {"kind": "cv.done", "rows": _filter_valid(merged), "meta": meta}
        return

    tooling, narrative, veto_ch = parse_subagent_tool_payloads(all_messages)
    ai_rows = shards_to_preference_rows(tooling, narrative, veto_ch)
    meta["shard_counts"] = {
        "tooling_items": len(tooling.items) if tooling else 0,
        "narrative_domains": len(narrative.domains) if narrative else 0,
        "veto": len(veto_ch.vetoes) if veto_ch else 0,
    }
    merged = merge_facets(ai_rows, regex_rows)
    yield {"kind": "cv.done", "rows": _filter_valid(merged), "meta": meta}
