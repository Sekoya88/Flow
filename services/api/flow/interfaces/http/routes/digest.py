from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from flow.infrastructure.observability.logging import get_logger
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/digest", tags=["Research Digest"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class DigestConfigIn(BaseModel):
    workspace_id: UUID
    enabled: bool = False
    schedule_hour: int = 8
    min_relevance_score: float = 0.5
    arxiv_categories: list[str] = ["cs.AI", "cs.LG", "cs.CL"]
    custom_sources: list[str] = []
    user_interests: str = ""
    obsidian_mode: str = "filesystem"
    obsidian_vault_path: str | None = None
    obsidian_api_url: str | None = None
    obsidian_cloud_bucket: str | None = None


class DigestRunIn(BaseModel):
    workspace_id: UUID


class PaperPatchIn(BaseModel):
    status: str  # unread | read | archived


class ExportObsidianIn(BaseModel):
    workspace_id: UUID
    paper_ids: list[UUID]


class SynthesisIn(BaseModel):
    workspace_id: UUID
    limit: int = 20


class EmbedKnowledgeIn(BaseModel):
    workspace_id: UUID
    paper_ids: list[UUID]


class DigestExportOut(BaseModel):
    exported: int
    paths: list[str]
    index_path: str | None
    vault_path: str


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _assert_workspace(user_id: UUID, workspace_id: UUID, repo: FlowRepository) -> None:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    if workspace_id not in {r["id"] for r in ws_rows}:
        raise HTTPException(status_code=403, detail="workspace not allowed")


def _safe_write(vault_root: Path, note_path: str, content: str) -> Path:
    """Write content to vault_root/note_path, rejecting path traversal.

    Raises ValueError if note_path is absolute or resolves outside vault_root.
    """
    if Path(note_path).is_absolute():
        raise ValueError(f"path traversal rejected: absolute path {note_path!r}")
    resolved = (vault_root / note_path).resolve()
    if not resolved.is_relative_to(vault_root.resolve()):
        raise ValueError(f"path traversal rejected: {note_path!r} escapes vault root")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return resolved


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/config")
async def get_digest_config(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await _assert_workspace(user_id, workspace_id, repo)
    row = await repo._pool.fetchrow("SELECT * FROM workspace_digest_config WHERE workspace_id = $1", workspace_id)
    if not row:
        raise HTTPException(status_code=404, detail="Digest not configured for this workspace")
    return dict(row)


@router.put("/config")
async def upsert_digest_config(
    body: DigestConfigIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await _assert_workspace(user_id, body.workspace_id, repo)
    row = await repo._pool.fetchrow(
        """
        INSERT INTO workspace_digest_config
            (workspace_id, enabled, schedule_hour, min_relevance_score,
             arxiv_categories, custom_sources, user_interests, obsidian_mode,
             obsidian_vault_path, obsidian_api_url, obsidian_cloud_bucket)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        ON CONFLICT (workspace_id) DO UPDATE SET
            enabled                = EXCLUDED.enabled,
            schedule_hour          = EXCLUDED.schedule_hour,
            min_relevance_score    = EXCLUDED.min_relevance_score,
            arxiv_categories       = EXCLUDED.arxiv_categories,
            custom_sources         = EXCLUDED.custom_sources,
            user_interests         = EXCLUDED.user_interests,
            obsidian_mode          = EXCLUDED.obsidian_mode,
            obsidian_vault_path    = EXCLUDED.obsidian_vault_path,
            obsidian_api_url       = EXCLUDED.obsidian_api_url,
            obsidian_cloud_bucket  = EXCLUDED.obsidian_cloud_bucket,
            updated_at             = now()
        RETURNING *
        """,
        body.workspace_id,
        body.enabled,
        body.schedule_hour,
        body.min_relevance_score,
        body.arxiv_categories,
        body.custom_sources,
        body.user_interests,
        body.obsidian_mode,
        body.obsidian_vault_path,
        body.obsidian_api_url,
        body.obsidian_cloud_bucket,
    )
    return dict(row)


@router.post("/run", status_code=202)
async def run_digest_now(
    body: DigestRunIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Trigger a research digest immediately. Returns job info."""
    from flow.infrastructure.queue.client import get_arq_pool

    await _assert_workspace(user_id, body.workspace_id, repo)
    config_row = await repo._pool.fetchrow(
        "SELECT * FROM workspace_digest_config WHERE workspace_id = $1",
        body.workspace_id,
    )
    config = dict(config_row) if config_row else {}

    arq_pool = await get_arq_pool()
    job = await arq_pool.enqueue_job(
        "run_research_digest",
        str(body.workspace_id),
        config,
    )
    logger.info("digest.job.enqueued", workspace_id=str(body.workspace_id), job_id=job.job_id)
    return {"job_id": job.job_id, "status": "queued"}


@router.get("/papers")
async def list_digest_papers(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    status: str | None = None,
    category: str | None = None,
    relevance_min: float = Query(default=0.0, ge=0.0, le=1.0),
    limit: int = Query(default=20, le=100),
    offset: int = 0,
) -> list:
    await _assert_workspace(user_id, workspace_id, repo)
    conditions = ["workspace_id = $1"]
    params: list = [workspace_id]
    i = 2
    if status:
        conditions.append(f"status = ${i}")
        params.append(status)
        i += 1
    if relevance_min > 0:
        conditions.append(f"relevance_score >= ${i}")
        params.append(relevance_min)
        i += 1

    where = " AND ".join(conditions)
    rows = await repo._pool.fetch(
        f"""
        SELECT * FROM digest_papers
        WHERE {where}
        ORDER BY digested_at DESC
        LIMIT ${i} OFFSET ${i + 1}
        """,
        *params,
        limit,
        offset,
    )
    return [dict(r) for r in rows]


@router.get("/history")
async def list_digest_history(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    limit: int = Query(default=30, le=365),
    offset: int = 0,
) -> list:
    """Paginated history of digest runs — grouped by day with aggregate stats."""
    await _assert_workspace(user_id, workspace_id, repo)
    rows = await repo._pool.fetch(
        """
        SELECT
            digested_at::date                          AS run_date,
            COUNT(*)                                   AS paper_count,
            ROUND(AVG(relevance_score)::numeric, 3)    AS avg_relevance,
            COUNT(*) FILTER (WHERE status = 'unread')  AS unread_count,
            COUNT(*) FILTER (WHERE status = 'read')    AS read_count,
            array_agg(DISTINCT unnest) FILTER (WHERE unnest IS NOT NULL) AS categories
        FROM digest_papers dp,
             LATERAL unnest(dp.categories) AS unnest
        WHERE dp.workspace_id = $1
        GROUP BY run_date
        ORDER BY run_date DESC
        LIMIT $2 OFFSET $3
        """,
        workspace_id,
        limit,
        offset,
    )
    return [dict(r) for r in rows]


@router.post("/papers/{paper_id}/summarize")
async def summarize_paper(
    paper_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Re-run LLM summarization on a single paper and update tldr + key_insights."""
    row = await repo._pool.fetchrow("SELECT * FROM digest_papers WHERE id = $1", paper_id)
    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")
    await _assert_workspace(user_id, row["workspace_id"], repo)

    import json as _json

    from langchain_core.messages import HumanMessage, SystemMessage

    from flow.config import get_settings
    from flow.infrastructure.llm.providers import get_chat_model

    settings = get_settings()
    fallback_keys = {"openai": settings.openai_api_key, "anthropic": settings.anthropic_api_key}
    llm = get_chat_model({"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.1}, fallback_keys)
    if llm is None:
        raise HTTPException(status_code=503, detail="No LLM provider configured")

    abstract = row["abstract"] or ""
    resp = await llm.ainvoke(
        [
            SystemMessage(content="You are a research assistant. Be concise."),
            HumanMessage(
                content=(
                    f"Paper: {row['title']}\n\nAbstract: {abstract[:1500]}\n\n"
                    'Reply with JSON only: {"tldr": "one sentence", "key_insights": "2-3 bullet points"}'
                )
            ),
        ]
    )
    text = resp.content if hasattr(resp, "content") else str(resp)
    start = text.find("{")
    end = text.rfind("}") + 1
    parsed = _json.loads(text[start:end]) if start >= 0 else {}
    ki = parsed.get("key_insights")
    if isinstance(ki, list):
        ki = "\n".join(f"- {item}" for item in ki)

    updated = await repo._pool.fetchrow(
        "UPDATE digest_papers SET tldr = $1, key_insights = $2 WHERE id = $3 RETURNING tldr, key_insights",
        parsed.get("tldr"),
        ki,
        paper_id,
    )
    return dict(updated)


@router.patch("/papers/{paper_id}")
async def patch_digest_paper(
    paper_id: UUID,
    body: PaperPatchIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    row = await repo._pool.fetchrow("SELECT workspace_id FROM digest_papers WHERE id = $1", paper_id)
    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")
    await _assert_workspace(user_id, row["workspace_id"], repo)

    updated = await repo._pool.fetchrow(
        "UPDATE digest_papers SET status = $2 WHERE id = $1 RETURNING *",
        paper_id,
        body.status,
    )
    return dict(updated)


@router.post("/papers/export-obsidian")
async def export_papers_to_obsidian(
    body: ExportObsidianIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Write selected papers' Obsidian markdown to the configured vault path."""
    from datetime import date

    await _assert_workspace(user_id, body.workspace_id, repo)
    if not body.paper_ids:
        raise HTTPException(status_code=400, detail="No paper IDs provided")

    placeholders = ", ".join(f"${i + 2}" for i in range(len(body.paper_ids)))
    rows = await repo._pool.fetch(
        f"SELECT id, title, abstract, tldr, key_insights, authors, categories, "
        f"arxiv_id, source_url, summary_md, obsidian_path, relevance_score "
        f"FROM digest_papers WHERE workspace_id = $1 AND id IN ({placeholders})",
        body.workspace_id,
        *body.paper_ids,
    )

    config_row = await repo._pool.fetchrow(
        "SELECT obsidian_vault_path FROM workspace_digest_config WHERE workspace_id = $1",
        body.workspace_id,
    )
    vault_path = (config_row["obsidian_vault_path"] if config_row else None) or "/vault"
    vault_root = Path(vault_path).expanduser().resolve()

    today = date.today().isoformat()
    written = 0
    skipped = 0
    for row in rows:
        # Use stored summary_md if available, else generate from fields
        content = row["summary_md"]
        if not content:
            arxiv_id = row["arxiv_id"] or ""
            authors_yaml = "\n".join(f"  - {a}" for a in (row["authors"] or []))
            cats_yaml = "\n".join(f"  - {c}" for c in (row["categories"] or []))
            tldr = row["tldr"] or "_No summary available._"
            ki = row["key_insights"] or "_No insights available._"
            if isinstance(ki, list):
                ki = "\n".join(f"- {item}" for item in ki)
            content = f"""---
title: "{(row["title"] or "").replace('"', "'")}"
date: {today}
source: {row["source_url"] or ""}
arxiv_id: {arxiv_id}
authors:
{authors_yaml or "  - Unknown"}
categories:
{cats_yaml or "  - unknown"}
relevance_score: {float(row["relevance_score"] or 0):.2f}
status: unread
type: research-paper
---

# {row["title"]}

> [!abstract] TL;DR
> {tldr}

## 🔑 Key Insights
{ki}

## 📖 Abstract
{(row["abstract"] or "")[:2000]}

## 🔗 References
- Source: {row["source_url"] or "N/A"}
- ArXiv: {"https://arxiv.org/abs/" + arxiv_id if arxiv_id else "N/A"}
"""
        obsidian_path = row["obsidian_path"]
        if not obsidian_path:
            safe = (row["arxiv_id"] or (row["title"] or "paper")[:40]).replace("/", "-").replace(":", "")
            obsidian_path = f"Research/Digest/{today}/{safe}.md"

        try:
            _safe_write(vault_root, obsidian_path, content)
            written += 1
        except ValueError:
            logger.warning("digest.export.path_traversal_rejected", paper_id=str(row["id"]))
            skipped += 1
        except Exception:
            logger.warning("digest.export.vault_write_failed", paper_id=str(row["id"]))
            skipped += 1

    logger.info("digest.export.done", written=written, skipped=skipped)
    return {"written": written, "skipped": skipped, "vault_path": vault_path}


@router.post("/synthesize")
async def synthesize_knowledge(
    body: SynthesisIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """LLM synthesis of recent papers: topics, methods, datasets, key findings."""
    import json as _json
    import os
    from datetime import date
    from uuid import UUID as _UUID

    from langchain_core.messages import HumanMessage, SystemMessage

    from flow.config import get_settings
    from flow.infrastructure.llm.providers import get_chat_model

    await _assert_workspace(user_id, body.workspace_id, repo)

    rows = await repo._pool.fetch(
        """
        SELECT title, tldr, key_insights, categories
        FROM digest_papers
        WHERE workspace_id = $1 AND (tldr IS NOT NULL OR key_insights IS NOT NULL)
        ORDER BY digested_at DESC
        LIMIT $2
        """,
        body.workspace_id,
        body.limit,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No summarized papers found — run a digest first")

    papers_text = "\n\n".join(f"**{r['title']}**\nTL;DR: {r['tldr'] or 'N/A'}\nInsights: {r['key_insights'] or 'N/A'}" for r in rows)

    settings = get_settings()
    fallback_keys = {"openai": settings.openai_api_key, "anthropic": settings.anthropic_api_key}
    llm = get_chat_model({"provider": "anthropic", "model": "claude-haiku-4-5-20251001", "temperature": 0.2}, fallback_keys) or get_chat_model(
        {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.2}, fallback_keys
    )
    if llm is None:
        raise HTTPException(status_code=503, detail="No LLM provider configured")

    resp = await llm.ainvoke(
        [
            SystemMessage(content="You are a research synthesis assistant. Reply with JSON only."),
            HumanMessage(
                content=(
                    f"Synthesize these {len(rows)} research papers into a structured knowledge summary.\n\n"
                    f"{papers_text[:6000]}\n\n"
                    "Reply with JSON only:\n"
                    '{"topics": ["theme1", "..."], "methods": ["method1", "..."], "datasets": ["ds1", "..."], '
                    '"key_findings": "3-5 paragraph synthesis of the research landscape", '
                    '"open_questions": ["q1", "..."]}'
                )
            ),
        ]
    )
    text = resp.content if hasattr(resp, "content") else str(resp)
    start = text.find("{")
    end = text.rfind("}") + 1
    parsed = _json.loads(text[start:end]) if start >= 0 else {}

    today = date.today().isoformat()
    nl = "\n"
    synthesis_md = f"""---
date: {today}
type: synthesis
tags:
  - research
  - synthesis
  - {today}
paper_count: {len(rows)}
---
# Research Synthesis — {today}

## 🏷 Topics
{nl.join(f"- {t}" for t in parsed.get("topics", []))}

## 🛠 Methods & Approaches
{nl.join(f"- {m}" for m in parsed.get("methods", []))}

## 📦 Datasets & Benchmarks
{nl.join(f"- {d}" for d in parsed.get("datasets", []))}

## 🔑 Key Findings
{parsed.get("key_findings", "_No findings generated._")}

## ❓ Open Questions
{nl.join(f"- {q}" for q in parsed.get("open_questions", []))}

---
*Generated from {len(rows)} papers on {today}*
"""

    config_row = await repo._pool.fetchrow(
        "SELECT obsidian_mode, obsidian_vault_path FROM workspace_digest_config WHERE workspace_id = $1",
        body.workspace_id,
    )
    if config_row and config_row["obsidian_mode"] == "filesystem":
        vault_path = config_row["obsidian_vault_path"] or "/vault"
        full_path = os.path.join(vault_path, f"Research/Synthesis/{today}.md")
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(synthesis_md)
            logger.info("digest.synthesize.vault_written", path=full_path)
        except Exception:
            logger.warning("digest.synthesize.vault_write_failed", path=full_path)

    try:
        await repo._pool.execute(
            """
            INSERT INTO kg_nodes (workspace_id, label, node_type, summary, metadata)
            VALUES ($1, $2, 'synthesis', $3, $4::jsonb)
            ON CONFLICT (workspace_id, label, node_type) DO UPDATE
                SET summary = EXCLUDED.summary, metadata = EXCLUDED.metadata, updated_at = now()
            """,
            _UUID(str(body.workspace_id)),
            f"Research Synthesis {today}",
            parsed.get("key_findings", "")[:500],
            _json.dumps({"topics": parsed.get("topics", []), "date": today, "paper_count": len(rows)}),
        )
    except Exception:
        logger.warning("digest.synthesize.kg_node_failed")

    return {**parsed, "synthesis_md": synthesis_md, "paper_count": len(rows)}


@router.delete("/papers/{paper_id}", status_code=204, response_model=None)
async def delete_digest_paper(
    paper_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    delete_from_vault: bool = False,
) -> None:
    """Delete a paper from the DB and optionally from the Obsidian vault."""
    import os

    row = await repo._pool.fetchrow("SELECT workspace_id, obsidian_path, title FROM digest_papers WHERE id = $1", paper_id)
    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")
    await _assert_workspace(user_id, row["workspace_id"], repo)

    if delete_from_vault and row["obsidian_path"]:
        config_row = await repo._pool.fetchrow(
            "SELECT obsidian_vault_path FROM workspace_digest_config WHERE workspace_id = $1",
            row["workspace_id"],
        )
        if config_row:
            vault_path = config_row["obsidian_vault_path"] or "/vault"
            try:
                os.remove(os.path.join(vault_path, row["obsidian_path"]))
            except Exception:
                pass

    await repo._pool.execute(
        "DELETE FROM kg_nodes WHERE workspace_id = $1 AND label = $2 AND node_type = 'paper'",
        row["workspace_id"],
        row["title"][:500],
    )
    await repo._pool.execute("DELETE FROM digest_papers WHERE id = $1", paper_id)
    logger.info("digest.paper.deleted", paper_id=str(paper_id))


@router.post("/papers/embed-knowledge")
async def embed_papers_as_knowledge(
    body: EmbedKnowledgeIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Embed selected papers as dense+sparse vectors into Qdrant for agent retrieval."""
    import asyncio as _asyncio

    from langchain_openai import OpenAIEmbeddings

    from flow.config import get_settings
    from flow.infrastructure.agentic_rag.qdrant_hybrid import (
        get_qdrant_client,
        setup_collection,
        sparse_encode_text,
        upsert_knowledge_chunk_async,
    )

    await _assert_workspace(user_id, body.workspace_id, repo)
    settings = get_settings()

    if not settings.qdrant_url or not settings.qdrant_url.strip():
        raise HTTPException(status_code=503, detail="Qdrant not configured (FLOW_QDRANT_URL missing)")
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")
    if not body.paper_ids:
        raise HTTPException(status_code=400, detail="No paper IDs provided")

    placeholders = ", ".join(f"${i + 2}" for i in range(len(body.paper_ids)))
    rows = await repo._pool.fetch(
        f"SELECT id, title, tldr, abstract FROM digest_papers WHERE workspace_id = $1 AND id IN ({placeholders})",
        body.workspace_id,
        *body.paper_ids,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No papers found")

    texts = [f"{r['title']}\n{r['tldr'] or ''}\n{r['abstract'] or ''}" for r in rows]

    embedder = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=settings.openai_api_key)
    dense_vectors = await embedder.aembed_documents(texts)

    base = settings.qdrant_url.strip().rstrip("/")
    url = base if base.startswith("http") else f"http://{base}"
    client = get_qdrant_client(url)
    coll = settings.qdrant_collection
    await _asyncio.to_thread(setup_collection, client, coll)

    embedded = 0
    for i, row in enumerate(rows):
        try:
            si, sv = await sparse_encode_text(texts[i])
            # chunk_pk is stable per paper: derived from paper UUID bytes
            await upsert_knowledge_chunk_async(
                client,
                collection=coll,
                workspace_id=body.workspace_id,
                source_id=row["id"],
                title=row["title"],
                chunk_pk=row["id"].int % (2**62),
                content=texts[i],
                dense_embedding=dense_vectors[i],
                sparse_indices=si,
                sparse_values=sv,
            )
            embedded += 1
        except Exception:
            logger.warning("digest.embed_knowledge.upsert_failed", paper_id=str(row["id"]))

    logger.info("digest.embed_knowledge.done", embedded=embedded, workspace_id=str(body.workspace_id))
    return {"embedded": embedded}


@router.post("/runs/{run_id}/export-obsidian", response_model=DigestExportOut)
async def export_digest_to_obsidian(
    run_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> DigestExportOut:
    """Write digest notes to the configured local Obsidian vault."""
    import os

    # Verify run belongs to one of this user's workspaces
    ws_rows = await repo.list_workspaces_for_user(user_id)
    if not ws_rows:
        raise HTTPException(status_code=403, detail="no workspace")
    ws_ids = {r["id"] for r in ws_rows}

    run_row = await repo._pool.fetchrow(
        "SELECT workspace_id FROM digest_runs WHERE id = $1",
        run_id,
    )
    if run_row is None or run_row["workspace_id"] not in ws_ids:
        raise HTTPException(status_code=404, detail="digest run not found")

    ws_id = run_row["workspace_id"]
    vault_str = await repo.get_workspace_vault_path(ws_id) or os.environ.get("FLOW_OBSIDIAN_VAULT_PATH")
    if not vault_str:
        raise HTTPException(
            status_code=400,
            detail="Obsidian vault path not configured. Set it in workspace settings or FLOW_OBSIDIAN_VAULT_PATH env var.",
        )

    vault_root = Path(vault_str).expanduser().resolve()
    if not vault_root.exists():
        raise HTTPException(status_code=400, detail="Vault path does not exist on this server.")

    papers = await repo.get_digest_run_papers(run_id)
    written_paths: list[str] = []
    index_path: str | None = None

    for paper in papers:
        note_path: str | None = paper["obsidian_path"]
        content: str | None = paper["summary_md"]
        if not note_path or not content:
            continue
        try:
            out = _safe_write(vault_root, note_path, content)
            written_paths.append(str(out.relative_to(vault_root)))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid note path in digest paper.") from None

    # Write index note with wikilinks to each paper
    if papers:
        from datetime import date

        today = date.today().isoformat()
        paper_links = "\n".join(f"- [[{p['obsidian_path'].replace('.md', '')}|{p['title'][:70]}]]" for p in papers if p.get("obsidian_path"))
        index_content = (
            f"---\ndate: {today}\ntype: daily-digest\ntags:\n  - research\n  - digest\n---\n"
            f"# Research Digest — {today}\n\n{paper_links or '_No papers._'}\n"
        )
        index_rel = f"Research/Digest/{today}/index.md"
        try:
            _safe_write(vault_root, index_rel, index_content)
            index_path = index_rel
        except ValueError:
            pass

    return DigestExportOut(
        exported=len(written_paths),
        paths=written_paths,
        index_path=index_path,
        vault_path=str(vault_root),
    )


@router.get("/knowledge")
async def list_embedded_knowledge(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Return papers embedded in Qdrant for this workspace."""
    from qdrant_client.http import models as qmodels

    from flow.config import get_settings
    from flow.infrastructure.agentic_rag.qdrant_hybrid import get_qdrant_client

    await _assert_workspace(user_id, workspace_id, repo)
    settings = get_settings()

    if not settings.qdrant_url or not settings.qdrant_url.strip():
        return {"available": False, "count": 0, "papers": []}

    base = settings.qdrant_url.strip().rstrip("/")
    url = base if base.startswith("http") else f"http://{base}"
    client = get_qdrant_client(url)
    coll = settings.qdrant_collection

    try:
        import asyncio as _asyncio

        results, _ = await _asyncio.to_thread(
            client.scroll,
            collection_name=coll,
            scroll_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="workspace_id",
                        match=qmodels.MatchValue(value=str(workspace_id)),
                    )
                ]
            ),
            limit=100,
            with_payload=True,
            with_vectors=False,
        )
        papers = [{"id": str(r.id), "title": r.payload.get("title", ""), "tldr": r.payload.get("tldr")} for r in results]
        return {"available": True, "count": len(papers), "papers": papers}
    except Exception:
        return {"available": False, "count": 0, "papers": []}
