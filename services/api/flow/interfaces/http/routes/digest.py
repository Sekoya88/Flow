from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from flow.interfaces.http.deps import get_current_user_id, get_repo
from flow.infrastructure.persistence.repo import FlowRepository

router = APIRouter(prefix="/api/v1/digest", tags=["Research Digest"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class DigestConfigIn(BaseModel):
    workspace_id: UUID
    enabled: bool = False
    schedule_hour: int = 8
    min_relevance_score: float = 0.5
    arxiv_categories: list[str] = ["cs.AI", "cs.LG", "cs.CL"]
    custom_sources: list[str] = []
    obsidian_mode: str = "filesystem"
    obsidian_vault_path: Optional[str] = None
    obsidian_api_url: Optional[str] = None
    obsidian_cloud_bucket: Optional[str] = None


class DigestRunIn(BaseModel):
    workspace_id: UUID


class PaperPatchIn(BaseModel):
    status: str  # unread | read | archived


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _assert_workspace(
    user_id: UUID, workspace_id: UUID, repo: FlowRepository
) -> None:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    if workspace_id not in {r["id"] for r in ws_rows}:
        raise HTTPException(status_code=403, detail="workspace not allowed")


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/config")
async def get_digest_config(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await _assert_workspace(user_id, workspace_id, repo)
    row = await repo._pool.fetchrow(
        "SELECT * FROM workspace_digest_config WHERE workspace_id = $1", workspace_id
    )
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
             arxiv_categories, custom_sources, obsidian_mode,
             obsidian_vault_path, obsidian_api_url, obsidian_cloud_bucket)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (workspace_id) DO UPDATE SET
            enabled                = EXCLUDED.enabled,
            schedule_hour          = EXCLUDED.schedule_hour,
            min_relevance_score    = EXCLUDED.min_relevance_score,
            arxiv_categories       = EXCLUDED.arxiv_categories,
            custom_sources         = EXCLUDED.custom_sources,
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
    from flow.config import get_settings

    await _assert_workspace(user_id, body.workspace_id, repo)
    config_row = await repo._pool.fetchrow(
        "SELECT * FROM workspace_digest_config WHERE workspace_id = $1",
        body.workspace_id,
    )
    config = dict(config_row) if config_row else {}

    arq_pool = await get_arq_pool(get_settings().redis_url)
    job = await arq_pool.enqueue_job(
        "run_research_digest",
        str(body.workspace_id),
        config,
    )
    return {"job_id": job.job_id, "status": "queued"}


@router.get("/papers")
async def list_digest_papers(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    status: Optional[str] = None,
    category: Optional[str] = None,
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


@router.patch("/papers/{paper_id}")
async def patch_digest_paper(
    paper_id: UUID,
    body: PaperPatchIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    row = await repo._pool.fetchrow(
        "SELECT workspace_id FROM digest_papers WHERE id = $1", paper_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")
    await _assert_workspace(user_id, row["workspace_id"], repo)

    updated = await repo._pool.fetchrow(
        "UPDATE digest_papers SET status = $2 WHERE id = $1 RETURNING *",
        paper_id,
        body.status,
    )
    return dict(updated)
