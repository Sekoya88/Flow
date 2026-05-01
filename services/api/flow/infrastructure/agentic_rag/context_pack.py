from __future__ import annotations

from typing import Any


def flow_kb_label(index_1_based: int) -> str:
    return f"FLOW_KB_{index_1_based:03d}"


def format_graded_context(graded_docs: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for i, doc in enumerate(graded_docs, 1):
        label = flow_kb_label(i)
        meta = doc.get("metadata") or {}
        title = str(meta.get("title") or meta.get("source") or "unknown")
        grade = doc.get("grade") or {}
        combined = float(grade.get("combined_score", 0.0))
        content = str(doc.get("content", ""))
        parts.append(f"[{label}] graded_score={combined:.3f}\nSource: {title}\n{content}")
    return "\n\n---\n\n".join(parts)


def build_rag_messages(*, graded_docs: list[dict[str, Any]], web_results: list[str]) -> list[str]:
    blocks: list[str] = []
    if graded_docs:
        blocks.append("## Retrieved knowledge\n" + format_graded_context(graded_docs))
    if web_results:
        web_section = "\n---\n".join(web_results[:5])
        blocks.append("## Web search results\n" + web_section)
    if not blocks:
        blocks.append("(No retrieved documents or web results.)")
    return ["\n\n".join(blocks)]
