"""5-node LangGraph for nightly research digest."""
from __future__ import annotations

import json
from typing import TypedDict
from uuid import UUID

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from flow.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class DigestState(TypedDict):
    workspace_id: str
    config: dict
    raw_papers: list[dict]
    filtered_papers: list[dict]
    enriched_papers: list[dict]
    obsidian_notes: list[dict]
    persisted_ids: list[str]


# ── Node 1: fetch_sources ─────────────────────────────────────────────────────


async def fetch_sources(state: DigestState) -> dict:
    config = state["config"]
    categories = config.get("arxiv_categories", ["cs.AI", "cs.LG", "cs.CL"])
    papers: list[dict] = []

    try:
        import arxiv

        client = arxiv.Client()
        query = " OR ".join(f"cat:{c}" for c in categories)
        search = arxiv.Search(query=query, max_results=50, sort_by=arxiv.SortCriterion.SubmittedDate)
        for result in client.results(search):
            papers.append(
                {
                    "title": result.title,
                    "abstract": result.summary,
                    "source_url": result.entry_id,
                    "arxiv_id": result.get_short_id(),
                    "authors": [str(a) for a in result.authors[:5]],
                    "categories": result.categories,
                    "published_at": result.published.isoformat() if result.published else None,
                }
            )
    except Exception:
        logger.exception("digest.fetch_sources.arxiv_failed")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get("https://huggingface.co/papers", headers={"Accept": "application/json"})
            if r.status_code == 200:
                data = r.json() if r.headers.get("content-type", "").startswith("application/json") else []
                for item in data[:20] if isinstance(data, list) else []:
                    papers.append(
                        {
                            "title": item.get("title", ""),
                            "abstract": item.get("abstract", ""),
                            "source_url": f"https://huggingface.co/papers/{item.get('id', '')}",
                            "arxiv_id": item.get("arxiv_id"),
                            "authors": item.get("authors", [])[:5],
                            "categories": [],
                            "published_at": item.get("publishedAt"),
                        }
                    )
    except Exception:
        logger.warning("digest.fetch_sources.hf_failed")

    logger.info("digest.fetch_sources.done", count=len(papers))
    return {"raw_papers": papers}


# ── Node 2: filter_by_interest ────────────────────────────────────────────────


async def filter_by_interest(state: DigestState) -> dict:
    from flow.config import get_settings
    from flow.infrastructure.llm.providers import get_chat_model

    config = state["config"]
    min_score = config.get("min_relevance_score", 0.5)
    categories = set(config.get("arxiv_categories", []))

    # pre-filter: drop papers with no title/abstract or zero category overlap
    candidates = []
    for paper in state["raw_papers"]:
        if not paper.get("title") or not paper.get("abstract"):
            continue
        paper_cats = set(paper.get("categories", []))
        if categories and paper_cats and not (categories & paper_cats):
            paper["relevance_score"] = 0.2
        else:
            paper["relevance_score"] = None  # needs LLM scoring
        candidates.append(paper)

    settings = get_settings()
    fallback_keys = {"openai": settings.openai_api_key, "anthropic": settings.anthropic_api_key}
    llm = get_chat_model(
        {"provider": "anthropic", "model": "claude-haiku-4-5-20251001", "temperature": 0.0},
        fallback_keys,
    ) or get_chat_model(
        {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.0}, fallback_keys
    )

    for paper in candidates:
        if paper["relevance_score"] is not None:
            continue
        if llm is None:
            paper["relevance_score"] = 0.6
            continue
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            prompt = (
                f"Rate the research relevance of this paper to the topics: {', '.join(sorted(categories)) or 'AI/ML'}.\n"
                f"Title: {paper['title']}\nAbstract: {paper['abstract'][:800]}\n"
                'Reply with JSON only: {"score": <float 0.0-1.0>}'
            )
            resp = await llm.ainvoke([
                SystemMessage(content="You are a research relevance scorer. Reply with JSON only."),
                HumanMessage(content=prompt),
            ])
            text = resp.content if hasattr(resp, "content") else str(resp)
            start = text.find("{")
            end = text.rfind("}") + 1
            parsed = json.loads(text[start:end]) if start >= 0 else {}
            paper["relevance_score"] = float(parsed.get("score", 0.5))
        except Exception:
            paper["relevance_score"] = 0.5

    filtered = [p for p in candidates if p["relevance_score"] >= min_score]
    filtered.sort(key=lambda p: p["relevance_score"], reverse=True)
    logger.info("digest.filter.done", kept=len(filtered), total=len(state["raw_papers"]))
    return {"filtered_papers": filtered[:20]}


# ── Node 3: summarize_papers ──────────────────────────────────────────────────


async def summarize_papers(state: DigestState) -> dict:
    from flow.config import get_settings
    from flow.infrastructure.llm.providers import get_chat_model

    settings = get_settings()
    fallback_keys = {"openai": settings.openai_api_key, "anthropic": settings.anthropic_api_key}
    llm = get_chat_model({"provider": "anthropic", "model": "claude-haiku-4-5-20251001", "temperature": 0.1}, fallback_keys) or get_chat_model({"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.1}, fallback_keys)
    if llm is None:
        logger.warning("digest.summarize.no_llm_skipping")
        enriched = [dict(p, tldr=None, key_insights=None) for p in state["filtered_papers"]]
        return {"enriched_papers": enriched}

    enriched = []
    for paper in state["filtered_papers"]:
        try:
            messages = [
                SystemMessage(content="You are a research assistant. Be concise."),
                HumanMessage(
                    content=(
                        f"Paper: {paper['title']}\n\nAbstract: {paper['abstract'][:1500]}\n\n"
                        "Reply with JSON: {\"tldr\": \"one sentence\", \"key_insights\": \"2-3 bullet points\"}"
                    )
                ),
            ]
            resp = await llm.ainvoke(messages)
            text = resp.content if hasattr(resp, "content") else str(resp)
            start = text.find("{")
            end = text.rfind("}") + 1
            parsed = json.loads(text[start:end]) if start >= 0 else {}
            paper = {**paper, "tldr": parsed.get("tldr"), "key_insights": parsed.get("key_insights")}
        except Exception:
            paper = {**paper, "tldr": None, "key_insights": None}
        enriched.append(paper)

    logger.info("digest.summarize.done", count=len(enriched))
    return {"enriched_papers": enriched}


# ── Node 4: format_obsidian ───────────────────────────────────────────────────


async def format_obsidian(state: DigestState) -> dict:
    from datetime import date

    today = date.today().isoformat()
    notes = []
    for paper in state["enriched_papers"]:
        arxiv_id = paper.get("arxiv_id") or ""
        authors_yaml = "\n".join(f"  - {a}" for a in paper.get("authors", []))
        cats_yaml = "\n".join(f"  - {c}" for c in paper.get("categories", []))
        relevance = paper.get("relevance_score", 0.0)

        frontmatter = f"""---
title: "{paper['title'].replace('"', "'")}"
date: {today}
created: {today}
source: {paper.get('source_url', '')}
arxiv_id: {arxiv_id}
authors:
{authors_yaml or '  - Unknown'}
categories:
{cats_yaml or '  - unknown'}
tags:
  - research
  - digest
  - {today}
relevance_score: {relevance:.2f}
flow_knowledge_id: null
status: unread
type: research-paper
---"""

        tldr = paper.get("tldr") or "_No summary generated._"
        key_insights = paper.get("key_insights") or "_No insights generated._"
        abstract = paper.get("abstract", "")[:2000]
        daily_link = f"[[Research/Digest/{today}/index]]"

        content = f"""{frontmatter}

# {paper['title']}

> [!abstract] TL;DR
> {tldr}

## 🔑 Key Insights
{key_insights}

## 📖 Abstract
{abstract}

## 🛠 Practical Applications
_To be filled._

## 📦 Models / Datasets / Benchmarks
_See paper for details._

## 🔗 References
- Source: {paper.get('source_url', 'N/A')}
- ArXiv: {f'https://arxiv.org/abs/{arxiv_id}' if arxiv_id else 'N/A'}
- Daily digest: {daily_link}

---
#research #digest #{today.replace('-', '')}"""

        safe_name = arxiv_id or paper['title'][:40].replace("/", "-").replace(":", "")
        notes.append(
            {
                "paper": paper,
                "path": f"Research/Digest/{today}/{safe_name}.md",
                "content": content,
            }
        )
    return {"obsidian_notes": notes}


# ── Node 5: persist ───────────────────────────────────────────────────────────


async def persist(state: DigestState) -> dict:
    import asyncpg
    from flow.config import get_settings

    workspace_id = state["workspace_id"]
    config = state["config"]
    settings = get_settings()
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)

    persisted_ids: list[str] = []
    for note in state["obsidian_notes"]:
        paper = note["paper"]
        try:
            row = await pool.fetchrow(
                """
                INSERT INTO digest_papers
                    (workspace_id, title, abstract, source_url, arxiv_id,
                     authors, categories, relevance_score, tldr, key_insights,
                     summary_md, obsidian_path, status, published_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,'unread',$13)
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                UUID(workspace_id),
                paper["title"],
                paper.get("abstract"),
                paper.get("source_url"),
                paper.get("arxiv_id"),
                paper.get("authors", []),
                paper.get("categories", []),
                paper.get("relevance_score", 0.0),
                paper.get("tldr"),
                paper.get("key_insights"),
                note["content"],
                note["path"],
                paper.get("published_at"),
            )
            if row:
                persisted_ids.append(str(row["id"]))
        except Exception:
            logger.exception("digest.persist.paper_failed", title=paper.get("title"))

    obsidian_mode = config.get("obsidian_mode", "filesystem")
    if obsidian_mode == "filesystem":
        vault_path = config.get("obsidian_vault_path", "/vault")
        import os

        for note in state["obsidian_notes"]:
            full_path = os.path.join(vault_path, note["path"])
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            try:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(note["content"])
            except Exception:
                logger.warning("digest.persist.vault_write_failed", path=full_path)

    await pool.close()
    logger.info("digest.persist.done", persisted=len(persisted_ids))
    return {"persisted_ids": persisted_ids}


# ── Graph ─────────────────────────────────────────────────────────────────────


def build_research_digest_graph():
    g = StateGraph(DigestState)
    g.add_node("fetch_sources", fetch_sources)
    g.add_node("filter_by_interest", filter_by_interest)
    g.add_node("summarize_papers", summarize_papers)
    g.add_node("format_obsidian", format_obsidian)
    g.add_node("persist", persist)

    g.set_entry_point("fetch_sources")
    g.add_edge("fetch_sources", "filter_by_interest")
    g.add_edge("filter_by_interest", "summarize_papers")
    g.add_edge("summarize_papers", "format_obsidian")
    g.add_edge("format_obsidian", "persist")
    g.add_edge("persist", END)

    return g.compile()


async def run_research_digest(workspace_id: str, config: dict) -> dict:
    graph = build_research_digest_graph()
    initial: DigestState = {
        "workspace_id": workspace_id,
        "config": config,
        "raw_papers": [],
        "filtered_papers": [],
        "enriched_papers": [],
        "obsidian_notes": [],
        "persisted_ids": [],
    }
    result = await graph.ainvoke(initial)
    return {"persisted": len(result.get("persisted_ids", []))}
