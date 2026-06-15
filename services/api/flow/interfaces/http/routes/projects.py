"""Research projects — CRUD + manual trigger endpoints."""

from __future__ import annotations

import os
import unicodedata
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from flow.infrastructure.observability.logging import get_logger
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["projects"])

# Default Obsidian subfolder for a project's curated references (thesis library).
_DEFAULT_REFERENCES_SUBFOLDER = "06-Thèse Pro/14-References"


async def _resolve_vault_root(repo: FlowRepository, workspace_id: UUID) -> Path:
    vault = await repo.get_workspace_vault_path(workspace_id) or os.environ.get("FLOW_OBSIDIAN_VAULT_PATH") or "/vault"
    return Path(vault).expanduser().resolve()


def _resolve_subfolder(vault_root: Path, subfolder: str) -> Path:
    """Resolve a subfolder under the vault, matching existing dirs by Unicode
    normalization (so an accented thesis folder like "06-Thèse Pro" maps to its
    real on-disk name whether stored NFC or NFD) and rejecting traversal."""
    cur = vault_root
    for seg in subfolder.split("/"):
        if not seg or seg in (".", ".."):
            continue
        target = unicodedata.normalize("NFC", seg)
        match: Path | None = None
        if cur.is_dir():
            for entry in cur.iterdir():
                if entry.is_dir() and unicodedata.normalize("NFC", entry.name) == target:
                    match = entry
                    break
        cur = match or (cur / seg)
    resolved = cur.resolve()
    if not resolved.is_relative_to(vault_root.resolve()):
        raise ValueError("subfolder escapes vault root")
    return resolved


def _slugify(text: str) -> str:
    keep = "".join(ch if ch.isalnum() or ch in " -_" else "" for ch in (text or "paper"))
    return ("-".join(keep.split()))[:80] or "paper"


def _paper_reference_md(paper: dict) -> str:
    """Build a self-contained Obsidian note for a single reference paper."""
    title = paper.get("title") or "Untitled"
    arxiv_id = paper.get("arxiv_id") or ""
    authors = paper.get("authors") or []
    categories = paper.get("categories") or []
    tldr = paper.get("tldr") or "_No summary._"
    abstract = (paper.get("abstract") or "")[:3000]
    ki = paper.get("key_insights")
    if isinstance(ki, list):
        ki = "\n".join(f"- {x}" for x in ki)
    ki = ki or "_N/A_"
    authors_yaml = "\n".join(f"  - {a}" for a in authors) or "  - Unknown"
    cats_yaml = "\n".join(f"  - {c}" for c in categories) or "  - unknown"
    link = paper.get("source_url") or (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "")
    return f"""---
title: "{title.replace('"', "'")}"
arxiv_id: {arxiv_id}
relevance_score: {float(paper.get("relevance_score") or 0):.2f}
authors:
{authors_yaml}
categories:
{cats_yaml}
type: reference
status: unread
---

# {title}

> [!abstract] TL;DR
> {tldr}

## Key Insights
{ki}

## Abstract
{abstract}

## Link
{link or "N/A"}
"""


class ProjectCreateIn(BaseModel):
    name: str
    goal: str = ""
    arxiv_categories: list[str] = []
    source_urls: list[str] = []
    cadence_cron: str = "0 9 * * 1"
    kg_namespace: str = ""
    enabled: bool = True


class ProjectPatchIn(BaseModel):
    name: str | None = None
    goal: str | None = None
    arxiv_categories: list[str] | None = None
    source_urls: list[str] | None = None
    cadence_cron: str | None = None
    kg_namespace: str | None = None
    enabled: bool | None = None


def _project_row(r: dict) -> dict:
    return {
        "id": str(r["id"]),
        "workspace_id": str(r["workspace_id"]),
        "name": r["name"],
        "goal": r["goal"] or "",
        "arxiv_categories": list(r["arxiv_categories"] or []),
        "source_urls": list(r["source_urls"] or []),
        "cadence_cron": r["cadence_cron"],
        "kg_namespace": r["kg_namespace"] or "",
        "enabled": r["enabled"],
        "created_at": r["created_at"].isoformat(),
        "last_run_at": r["last_run_at"].isoformat() if r["last_run_at"] else None,
    }


async def _assert_workspace_access(user_id: UUID, workspace_id: UUID, repo: FlowRepository) -> None:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    if workspace_id not in {r["id"] for r in ws_rows}:
        raise HTTPException(status_code=403, detail="workspace not allowed")


@router.get("/workspaces/{workspace_id}/projects")
async def list_projects(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await _assert_workspace_access(user_id, workspace_id, repo)
    rows = await repo._pool.fetch(
        "SELECT * FROM research_projects WHERE workspace_id = $1 ORDER BY created_at DESC",
        workspace_id,
    )
    return {"projects": [_project_row(dict(r)) for r in rows]}


@router.post("/workspaces/{workspace_id}/projects", status_code=status.HTTP_201_CREATED)
async def create_project(
    workspace_id: UUID,
    body: ProjectCreateIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await _assert_workspace_access(user_id, workspace_id, repo)
    row = await repo._pool.fetchrow(
        """
        INSERT INTO research_projects
            (workspace_id, name, goal, arxiv_categories, source_urls, cadence_cron, kg_namespace, enabled)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *
        """,
        workspace_id,
        body.name,
        body.goal,
        body.arxiv_categories,
        body.source_urls,
        body.cadence_cron,
        body.kg_namespace,
        body.enabled,
    )
    return _project_row(dict(row))


@router.get("/projects/{project_id}")
async def get_project(
    project_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    row = await repo._pool.fetchrow("SELECT * FROM research_projects WHERE id = $1", project_id)
    if not row:
        raise HTTPException(status_code=404, detail="project not found")
    await _assert_workspace_access(user_id, row["workspace_id"], repo)
    return _project_row(dict(row))


@router.patch("/projects/{project_id}")
async def patch_project(
    project_id: UUID,
    body: ProjectPatchIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    row = await repo._pool.fetchrow("SELECT * FROM research_projects WHERE id = $1", project_id)
    if not row:
        raise HTTPException(status_code=404, detail="project not found")
    await _assert_workspace_access(user_id, row["workspace_id"], repo)

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")

    set_clauses = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(updates))
    values = list(updates.values())
    updated = await repo._pool.fetchrow(
        f"UPDATE research_projects SET {set_clauses} WHERE id = $1 RETURNING *",
        project_id,
        *values,
    )
    return _project_row(dict(updated))


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> None:
    row = await repo._pool.fetchrow("SELECT workspace_id FROM research_projects WHERE id = $1", project_id)
    if not row:
        raise HTTPException(status_code=404, detail="project not found")
    await _assert_workspace_access(user_id, row["workspace_id"], repo)
    await repo._pool.execute("DELETE FROM research_projects WHERE id = $1", project_id)


@router.post("/projects/{project_id}/trigger")
async def trigger_project(
    request: Request,
    project_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Kick off a digest run for this project immediately."""
    row = await repo._pool.fetchrow("SELECT * FROM research_projects WHERE id = $1", project_id)
    if not row:
        raise HTTPException(status_code=404, detail="project not found")
    await _assert_workspace_access(user_id, row["workspace_id"], repo)

    project = dict(row)
    workspace_id_str = str(project["workspace_id"])

    # KG node count before run
    nodes_before_row = await repo._pool.fetchrow(
        "SELECT COUNT(*) AS cnt FROM kg_nodes WHERE workspace_id = $1",
        project["workspace_id"],
    )
    nodes_before = int(nodes_before_row["cnt"]) if nodes_before_row else 0

    try:
        from flow.infrastructure.graph.research_digest_graph import run_research_digest

        config: dict = {
            "arxiv_categories": list(project["arxiv_categories"] or []),
            "extra_urls": list(project["source_urls"] or []),
        }
        if project["goal"]:
            config["goal"] = project["goal"]
        if project["kg_namespace"]:
            config["kg_namespace"] = project["kg_namespace"]

        stream_hub = getattr(request.app.state, "stream_hub", None)
        result = await run_research_digest(workspace_id=workspace_id_str, config=config, stream_hub=stream_hub)
        digest_run_id_str: str | None = result.get("digest_run_id") if isinstance(result, dict) else None
        digest_run_uuid: UUID | None = UUID(digest_run_id_str) if digest_run_id_str else None

        # Authoritative count: rows actually written for this run. persisted_ids
        # from the graph state can be stale/empty even when papers were ingested
        # (papers move between runs on ON CONFLICT), so count the table directly.
        if digest_run_uuid is not None:
            persisted = await repo.count_digest_run_papers(digest_run_uuid)
        else:
            persisted = len(result.get("persisted_ids", [])) if isinstance(result, dict) else 0

        # KG node count after run
        nodes_after_row = await repo._pool.fetchrow(
            "SELECT COUNT(*) AS cnt FROM kg_nodes WHERE workspace_id = $1",
            project["workspace_id"],
        )
        nodes_after = int(nodes_after_row["cnt"]) if nodes_after_row else 0

        # Update project + record run
        await repo._pool.execute("UPDATE research_projects SET last_run_at = now() WHERE id = $1", project_id)
        await repo._pool.execute(
            """
            INSERT INTO project_runs
                (project_id, papers_processed, kg_nodes_before, kg_nodes_after, status, digest_run_id)
            VALUES ($1, $2, $3, $4, 'completed', $5)
            """,
            project_id,
            persisted,
            nodes_before,
            nodes_after,
            digest_run_uuid,
        )
        return {"status": "ok", "papers_processed": persisted, "digest_run_id": digest_run_id_str}
    except Exception as exc:
        await repo._pool.execute(
            """
            INSERT INTO project_runs
                (project_id, papers_processed, kg_nodes_before, kg_nodes_after, status, error_message)
            VALUES ($1, 0, $2, $2, 'failed', $3)
            """,
            project_id,
            nodes_before,
            str(exc)[:500],
        )
        logger.warning("project.trigger.failed", exc_info=True, project_id=str(project_id))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/projects/{project_id}/runs")
async def list_project_runs(
    project_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    row = await repo._pool.fetchrow("SELECT workspace_id FROM research_projects WHERE id = $1", project_id)
    if not row:
        raise HTTPException(status_code=404, detail="project not found")
    await _assert_workspace_access(user_id, row["workspace_id"], repo)

    runs = await repo._pool.fetch(
        """
        SELECT id, papers_processed, kg_nodes_before, kg_nodes_after, status, error_message, created_at, digest_run_id
        FROM project_runs WHERE project_id = $1
        ORDER BY created_at DESC LIMIT 50
        """,
        project_id,
    )
    return {
        "runs": [
            {
                "id": str(r["id"]),
                "papers_processed": r["papers_processed"],
                "kg_nodes_before": r["kg_nodes_before"],
                "kg_nodes_after": r["kg_nodes_after"],
                "kg_nodes_added": r["kg_nodes_after"] - r["kg_nodes_before"],
                "status": r["status"],
                "error_message": r["error_message"],
                "digest_run_id": str(r["digest_run_id"]) if r["digest_run_id"] else None,
                "created_at": r["created_at"].isoformat(),
            }
            for r in runs
        ]
    }


@router.get("/projects/{project_id}/papers")
async def list_project_papers(
    project_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Full transparency: every research paper this project has ingested."""
    row = await repo._pool.fetchrow("SELECT workspace_id FROM research_projects WHERE id = $1", project_id)
    if not row:
        raise HTTPException(status_code=404, detail="project not found")
    await _assert_workspace_access(user_id, row["workspace_id"], repo)

    papers = await repo.get_project_papers(project_id)
    return {
        "papers": [
            {
                "id": str(p["id"]),
                "title": p["title"],
                "abstract": p["abstract"],
                "source_url": p["source_url"],
                "arxiv_id": p["arxiv_id"],
                "authors": list(p["authors"] or []),
                "categories": list(p["categories"] or []),
                "relevance_score": float(p["relevance_score"]) if p["relevance_score"] is not None else None,
                "tldr": p["tldr"],
                "status": p["status"],
                "obsidian_path": p["obsidian_path"],
                "published_at": p["published_at"].isoformat() if p["published_at"] else None,
                "digest_run_id": str(p["digest_run_id"]) if p["digest_run_id"] else None,
            }
            for p in papers
        ]
    }


class ExportReferencesIn(BaseModel):
    subfolder: str | None = None
    paper_ids: list[UUID] | None = None  # None = export all project papers


@router.post("/projects/{project_id}/export-references")
async def export_project_references(
    project_id: UUID,
    body: ExportReferencesIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Write the project's papers as reference notes into an Obsidian subfolder."""
    row = await repo._pool.fetchrow("SELECT workspace_id FROM research_projects WHERE id = $1", project_id)
    if not row:
        raise HTTPException(status_code=404, detail="project not found")
    await _assert_workspace_access(user_id, row["workspace_id"], repo)

    subfolder = (body.subfolder or _DEFAULT_REFERENCES_SUBFOLDER).strip().strip("/")
    vault_root = await _resolve_vault_root(repo, row["workspace_id"])
    if not vault_root.exists():
        raise HTTPException(status_code=400, detail="Vault path does not exist on this server.")
    folder = _resolve_subfolder(vault_root, subfolder)
    folder.mkdir(parents=True, exist_ok=True)

    papers = [dict(p) for p in await repo.get_project_papers(project_id)]
    if body.paper_ids:
        wanted = {str(pid) for pid in body.paper_ids}
        papers = [p for p in papers if str(p["id"]) in wanted]

    written = 0
    skipped = 0
    for paper in papers:
        slug = _slugify(paper.get("title") or paper.get("arxiv_id") or "paper")
        try:
            (folder / f"{slug}.md").write_text(_paper_reference_md(paper), encoding="utf-8")
            written += 1
        except Exception:
            logger.warning("project.export_references.write_failed", project_id=str(project_id))
            skipped += 1

    return {"exported": written, "skipped": skipped, "folder": subfolder}


@router.get("/projects/{project_id}/references")
async def list_project_references(
    project_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    subfolder: str | None = None,
) -> dict:
    """List the .md reference notes already present in the project's Obsidian subfolder."""
    row = await repo._pool.fetchrow("SELECT workspace_id FROM research_projects WHERE id = $1", project_id)
    if not row:
        raise HTTPException(status_code=404, detail="project not found")
    await _assert_workspace_access(user_id, row["workspace_id"], repo)

    sub = (subfolder or _DEFAULT_REFERENCES_SUBFOLDER).strip().strip("/")
    vault_root = await _resolve_vault_root(repo, row["workspace_id"])
    try:
        folder = _resolve_subfolder(vault_root, sub)
    except ValueError:
        return {"folder": sub, "exists": False, "files": []}
    if not folder.is_dir():
        return {"folder": sub, "exists": False, "files": []}

    files = []
    for fp in sorted(folder.glob("*.md")):
        title = fp.stem
        try:
            with fp.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
        except Exception:
            pass
        files.append({"name": fp.name, "title": title})
    return {"folder": sub, "exists": True, "files": files}
