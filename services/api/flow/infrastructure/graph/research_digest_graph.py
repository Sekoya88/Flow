"""5-node LangGraph for nightly research digest."""

from __future__ import annotations

import asyncio
import json
from typing import Any, TypedDict
from uuid import UUID

import asyncpg
import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from flow.infrastructure.observability.callbacks import FlowCallbackHandler
from flow.infrastructure.observability.logging import get_logger
from flow.infrastructure.persistence.repo import FlowRepository

logger = get_logger(__name__)


class DigestState(TypedDict):
    workspace_id: str
    config: dict
    raw_papers: list[dict]
    filtered_papers: list[dict]
    enriched_papers: list[dict]
    obsidian_notes: list[dict]
    persisted_ids: list[str]
    stream_hub: Any  # Optional[ExecutionStreamHub] — in-memory only, no checkpointer
    digest_run_id: str | None  # UUID str of the digest_runs row for this run


# ── Node 1: fetch_sources ─────────────────────────────────────────────────────


async def fetch_sources(state: DigestState) -> dict:
    from datetime import datetime

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
                    "published_at": result.published,  # datetime.datetime — asyncpg needs this, not a string
                }
            )
    except Exception:
        logger.exception("digest.fetch_sources.arxiv_failed")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get("https://huggingface.co/api/daily_papers")
            if r.status_code == 200:
                data = r.json()
                for item in data[:20] if isinstance(data, list) else []:
                    paper = item.get("paper", item)
                    authors_raw = paper.get("authors", [])
                    authors = [a.get("name", str(a)) if isinstance(a, dict) else str(a) for a in authors_raw[:5]]
                    pub_str = paper.get("publishedAt")
                    try:
                        pub_dt: datetime | None = datetime.fromisoformat(pub_str.replace("Z", "+00:00")) if pub_str else None
                    except (ValueError, AttributeError):
                        pub_dt = None
                    papers.append(
                        {
                            "title": paper.get("title", ""),
                            "abstract": paper.get("summary", "") or paper.get("abstract", ""),
                            "source_url": f"https://huggingface.co/papers/{paper.get('id', '')}",
                            "arxiv_id": paper.get("id"),
                            "authors": authors,
                            "categories": [],
                            "published_at": pub_dt,
                        }
                    )
    except Exception:
        logger.warning("digest.fetch_sources.hf_failed")

    try:
        from flow.config import get_settings
        from flow.infrastructure.tools.web import run_tavily_search

        settings = get_settings()
        if settings.tavily_api_key:
            for cat in categories[:3]:
                results = await run_tavily_search(
                    query=f"new research paper {cat} 2025",
                    max_results=3,
                    api_key=settings.tavily_api_key,
                )
                for r in results:
                    if r.get("title") and r.get("content"):
                        papers.append(
                            {
                                "title": r["title"],
                                "abstract": r["content"][:800],
                                "source_url": r.get("url", ""),
                                "arxiv_id": None,
                                "authors": [],
                                "categories": [cat],
                                "published_at": None,
                            }
                        )
    except Exception:
        logger.warning("digest.fetch_sources.tavily_failed")

    custom_sources = config.get("custom_sources", [])
    if custom_sources:
        async with httpx.AsyncClient(timeout=20.0) as client:
            for url in custom_sources[:5]:
                try:
                    r = await client.get(url, follow_redirects=True)
                    if r.status_code != 200:
                        continue
                    try:
                        data = r.json()
                        items = data if isinstance(data, list) else data.get("papers", data.get("results", []))
                        for item in items[:10] if isinstance(items, list) else []:
                            if item.get("title"):
                                papers.append(
                                    {
                                        "title": item.get("title", ""),
                                        "abstract": item.get("abstract", item.get("summary", "")),
                                        "source_url": item.get("url", url),
                                        "arxiv_id": None,
                                        "authors": item.get("authors", [])[:5],
                                        "categories": [],
                                        "published_at": None,
                                    }
                                )
                    except Exception:
                        pass
                except Exception:
                    logger.warning("digest.fetch_sources.custom_url_failed", url=url)

    logger.info("digest.fetch_sources.done", count=len(papers))
    hub = state.get("stream_hub")
    if hub:
        await hub.publish_global(state["workspace_id"], "digest.fetch_done", {"count": len(papers)})
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
    ) or get_chat_model({"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.0}, fallback_keys)

    need_scoring = [p for p in candidates if p["relevance_score"] is None]

    hub = state.get("stream_hub")
    if hub:
        await hub.publish_global(state["workspace_id"], "digest.scoring", {"count": len(need_scoring)})
    logger.info("digest.filter.scoring_start", count=len(need_scoring))

    if llm is None:
        for p in need_scoring:
            p["relevance_score"] = 0.6
    else:
        sem = asyncio.Semaphore(10)

        user_interests = config.get("user_interests", "").strip()

        run_meta = RunnableConfig(
            metadata={
                "kind": "research_digest",
                "workspace_id": state["workspace_id"],
                "kg_namespace": config.get("kg_namespace", ""),
            }
        )

        async def score_one(paper: dict) -> float:
            async with sem:
                try:
                    interests_line = f"User interests: {user_interests}\n" if user_interests else ""
                    prompt = (
                        f"Rate the research relevance of this paper to the topics: "
                        f"{', '.join(sorted(categories)) or 'AI/ML'}.\n"
                        + interests_line
                        + f"Title: {paper['title']}\nAbstract: {paper['abstract'][:800]}\n"
                        'Reply with JSON only: {"score": <float 0.0-1.0>}'
                    )
                    resp = await llm.ainvoke(
                        [
                            SystemMessage(content="You are a research relevance scorer. Reply with JSON only."),
                            HumanMessage(content=prompt),
                        ],
                        config=run_meta,
                    )
                    text = resp.content if hasattr(resp, "content") else str(resp)
                    start = text.find("{")
                    end = text.rfind("}") + 1
                    parsed = json.loads(text[start:end]) if start >= 0 else {}
                    return float(parsed.get("score", 0.5))
                except Exception:
                    return 0.5

        scores = await asyncio.gather(*[score_one(p) for p in need_scoring])
        for paper, score in zip(need_scoring, scores, strict=False):
            paper["relevance_score"] = score

    logger.info("digest.filter.scoring_done", count=len(need_scoring))

    filtered = [p for p in candidates if p["relevance_score"] >= min_score]
    filtered.sort(key=lambda p: p["relevance_score"], reverse=True)
    kept = filtered[: config.get("max_papers", 50)]
    logger.info("digest.filter.done", kept=len(kept), total=len(state["raw_papers"]))
    hub = state.get("stream_hub")
    if hub:
        await hub.publish_global(
            state["workspace_id"],
            "digest.filter_done",
            {
                "kept": len(kept),
                "total": len(state["raw_papers"]),
            },
        )
    return {"filtered_papers": kept}


# ── Node 3: summarize_papers ──────────────────────────────────────────────────


async def summarize_papers(state: DigestState) -> dict:
    from flow.config import get_settings
    from flow.infrastructure.llm.providers import get_chat_model

    settings = get_settings()
    fallback_keys = {"openai": settings.openai_api_key, "anthropic": settings.anthropic_api_key}
    llm = get_chat_model({"provider": "anthropic", "model": "claude-haiku-4-5-20251001", "temperature": 0.1}, fallback_keys) or get_chat_model(
        {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.1}, fallback_keys
    )
    if llm is None:
        logger.warning("digest.summarize.no_llm_skipping")
        enriched = [dict(p, tldr=None, key_insights=None) for p in state["filtered_papers"]]
        return {"enriched_papers": enriched}

    logger.info("digest.summarize.start", count=len(state["filtered_papers"]))

    sem = asyncio.Semaphore(5)
    summarize_meta = RunnableConfig(
        metadata={
            "kind": "research_digest",
            "workspace_id": state["workspace_id"],
            "kg_namespace": state["config"].get("kg_namespace", ""),
        }
    )

    async def summarize_one(paper: dict) -> dict:
        async with sem:
            try:
                messages = [
                    SystemMessage(content="You are a research assistant. Be concise."),
                    HumanMessage(
                        content=(
                            f"Paper: {paper['title']}\n\nAbstract: {paper['abstract'][:1500]}\n\n"
                            'Reply with JSON: {"tldr": "one sentence", "key_insights": "2-3 bullet points"}'
                        )
                    ),
                ]
                resp = await llm.ainvoke(messages, config=summarize_meta)
                text = resp.content if hasattr(resp, "content") else str(resp)
                start = text.find("{")
                end = text.rfind("}") + 1
                parsed = json.loads(text[start:end]) if start >= 0 else {}
                ki = parsed.get("key_insights")
                if isinstance(ki, list):
                    ki = "\n".join(f"- {item}" for item in ki)
                return {**paper, "tldr": parsed.get("tldr"), "key_insights": ki}
            except Exception:
                return {**paper, "tldr": None, "key_insights": None}

    enriched = list(await asyncio.gather(*[summarize_one(p) for p in state["filtered_papers"]]))

    logger.info("digest.summarize.done", count=len(enriched))
    hub = state.get("stream_hub")
    if hub:
        await hub.publish_global(state["workspace_id"], "digest.summarize_done", {"count": len(enriched)})
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
title: "{paper["title"].replace('"', "'")}"
date: {today}
created: {today}
source: {paper.get("source_url", "")}
arxiv_id: {arxiv_id}
authors:
{authors_yaml or "  - Unknown"}
categories:
{cats_yaml or "  - unknown"}
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

        # Wikilinks for categories and authors (kepano/obsidian-skills style)
        cat_links = " ".join(f"[[Category/{c.replace('.', '-')}]]" for c in paper.get("categories", []))
        author_links = " ".join(f"[[Author/{a.replace(' ', '-')}]]" for a in paper.get("authors", [])[:3])

        content = f"""{frontmatter}

# {paper["title"]}

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

## 🏷 Topics
{cat_links or "_No categories._"}

## 👥 Authors
{author_links or "_Unknown._"}

## 🔗 References
- Source: {paper.get("source_url", "N/A")}
- ArXiv: {f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "N/A"}
- Daily digest: {daily_link}

---
#research #digest #{today.replace("-", "")}"""

        safe_name = arxiv_id or paper["title"][:40].replace("/", "-").replace(":", "")
        notes.append(
            {
                "paper": paper,
                "path": f"Research/Digest/{today}/{safe_name}.md",
                "content": content,
            }
        )

    # Second pass: add related papers section (shared categories)
    for i, note in enumerate(notes):
        shared = [n for j, n in enumerate(notes) if j != i and set(n["paper"].get("categories", [])) & set(note["paper"].get("categories", []))]
        if shared:
            related_links = "\n".join(f"- [[{n['path'].replace('.md', '')}|{n['paper']['title'][:60]}]]" for n in shared[:5])
            note["content"] += f"\n\n## 🔗 Related Papers\n{related_links}"

    # Daily index file — links to all papers in this digest
    paper_links = "\n".join(f"- [[{note['path'].replace('.md', '')}|{note['paper']['title'][:70]}]]" for note in notes)
    index_content = f"""---
date: {today}
type: daily-digest
tags:
  - research
  - digest
  - {today}
---
# Research Digest — {today}

{paper_links if paper_links else "_No papers in this digest._"}
"""
    notes.append(
        {
            "paper": {},
            "path": f"Research/Digest/{today}/index.md",
            "content": index_content,
        }
    )

    return {"obsidian_notes": notes}


# ── Node 5: persist ───────────────────────────────────────────────────────────


async def persist(state: DigestState) -> dict:
    from flow.config import get_settings

    workspace_id = state["workspace_id"]
    digest_run_id_val = state.get("digest_run_id")
    settings = get_settings()
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)
    try:
        persisted_ids: list[str] = []
        for note in state["obsidian_notes"]:
            paper = note["paper"]
            if not paper:  # daily index note has empty paper dict
                continue
            try:
                row = await pool.fetchrow(
                    """
                    INSERT INTO digest_papers
                        (workspace_id, title, abstract, source_url, arxiv_id,
                         authors, categories, relevance_score, tldr, key_insights,
                         summary_md, obsidian_path, status, published_at, digest_run_id)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,'unread',$13,$14)
                    ON CONFLICT (workspace_id, title) DO UPDATE SET
                        tldr = COALESCE(EXCLUDED.tldr, digest_papers.tldr),
                        key_insights = COALESCE(EXCLUDED.key_insights, digest_papers.key_insights),
                        relevance_score = EXCLUDED.relevance_score,
                        digest_run_id = EXCLUDED.digest_run_id,
                        status = 'unread'
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
                    UUID(digest_run_id_val) if digest_run_id_val else None,
                )
                if row:
                    persisted_ids.append(str(row["id"]))
            except Exception:
                logger.exception("digest.persist.paper_failed", title=paper.get("title"))

        # ── Knowledge graph nodes for each persisted paper ───────────────────
        paper_kg_ids: list[tuple[str, list[str]]] = []
        for note in state["obsidian_notes"]:
            paper = note["paper"]
            if not paper:
                continue
            try:
                row = await pool.fetchrow(
                    """
                    INSERT INTO kg_nodes
                        (workspace_id, label, node_type, summary, source_path, metadata)
                    VALUES ($1, $2, 'paper', $3, $4, $5::jsonb)
                    ON CONFLICT (workspace_id, label, node_type) DO UPDATE
                        SET summary = EXCLUDED.summary, source_path = EXCLUDED.source_path,
                            metadata = EXCLUDED.metadata, updated_at = now()
                    RETURNING id
                    """,
                    UUID(workspace_id),
                    paper["title"][:500],
                    (paper.get("tldr") or paper.get("abstract", ""))[:500],
                    paper.get("source_url"),
                    json.dumps(
                        {
                            "arxiv_id": paper.get("arxiv_id"),
                            "categories": paper.get("categories", []),
                            "relevance_score": paper.get("relevance_score"),
                        }
                    ),
                )
                if row:
                    paper_kg_ids.append((str(row["id"]), paper.get("categories", [])))
            except Exception:
                logger.warning("digest.persist.kg_node_failed", title=paper.get("title"))

        # ── Edges between papers sharing categories ───────────────────────────
        for i, (id_a, cats_a) in enumerate(paper_kg_ids):
            for id_b, cats_b in paper_kg_ids[i + 1 :]:
                shared = set(cats_a) & set(cats_b)
                if not shared:
                    continue
                weight = len(shared) / max(len(cats_a), len(cats_b), 1)
                try:
                    await pool.execute(
                        """
                        INSERT INTO kg_edges
                            (workspace_id, source_id, target_id, edge_type, weight)
                        VALUES ($1, $2, $3, 'co_category', $4)
                        ON CONFLICT (source_id, target_id, edge_type) DO NOTHING
                        """,
                        UUID(workspace_id),
                        UUID(id_a),
                        UUID(id_b),
                        weight,
                    )
                except Exception:
                    pass

        hub = state.get("stream_hub")
        if hub:
            await hub.publish_global(state["workspace_id"], "digest.persist_done", {"persisted": len(persisted_ids)})

        logger.info("digest.persist.done", persisted=len(persisted_ids))
        return {"persisted_ids": persisted_ids}
    finally:
        await pool.close()


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


async def run_research_digest(workspace_id: str, config: dict, stream_hub=None) -> dict:
    from flow.config import get_settings

    if stream_hub is not None:
        await stream_hub.publish_global(workspace_id, "digest.start", {"workspace_id": workspace_id})

    settings = get_settings()
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)
    repo = FlowRepository(pool)

    run_id: UUID | None = None
    result: dict = {}
    try:
        run_id = await repo.create_digest_run(
            UUID(workspace_id),
            source=config.get("source") or "arxiv",
        )

        graph = build_research_digest_graph()
        initial: DigestState = {
            "workspace_id": workspace_id,
            "config": config,
            "raw_papers": [],
            "filtered_papers": [],
            "enriched_papers": [],
            "obsidian_notes": [],
            "persisted_ids": [],
            "stream_hub": stream_hub,
            "digest_run_id": str(run_id),
        }
        run_config = RunnableConfig(callbacks=[FlowCallbackHandler(workspace_id=workspace_id)])
        result = await graph.ainvoke(initial, config=run_config)

        if run_id is not None:
            await repo.update_digest_run(
                run_id,
                status="done",
                paper_count=len(result.get("persisted_ids", [])),
                completed_at=True,
            )
    except Exception as e:
        logger.exception("digest.run.failed", workspace_id=workspace_id)
        if run_id is not None:
            try:
                await repo.update_digest_run(
                    run_id,
                    status="failed",
                    error=str(e),
                    completed_at=True,
                )
            except Exception:
                logger.warning("digest.run.update_failed_status_error")
        raise
    finally:
        await pool.close()
        persisted = len(result.get("persisted_ids", []))
        if stream_hub is not None:
            await stream_hub.publish_global(
                workspace_id,
                "digest.complete",
                {
                    "workspace_id": workspace_id,
                    "persisted": persisted,
                    "fetched": len(result.get("raw_papers", [])),
                    "filtered": len(result.get("filtered_papers", [])),
                },
            )

    # Surface digest_run_id + persisted_ids so callers (project trigger) can link
    # the run to its papers. Returning only {"persisted": …} left
    # project_runs.digest_run_id NULL, breaking the papers JOIN and paper counts.
    return {
        "persisted": persisted,
        "persisted_ids": result.get("persisted_ids", []),
        "digest_run_id": str(run_id) if run_id else None,
    }
