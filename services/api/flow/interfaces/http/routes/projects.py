"""Research projects — CRUD + manual trigger endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from flow.infrastructure.observability.logging import get_logger
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["projects"])


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
    row = await repo._pool.fetchrow(
        "SELECT * FROM research_projects WHERE id = $1", project_id
    )
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
    row = await repo._pool.fetchrow(
        "SELECT * FROM research_projects WHERE id = $1", project_id
    )
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
    row = await repo._pool.fetchrow(
        "SELECT workspace_id FROM research_projects WHERE id = $1", project_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="project not found")
    await _assert_workspace_access(user_id, row["workspace_id"], repo)
    await repo._pool.execute("DELETE FROM research_projects WHERE id = $1", project_id)


@router.post("/projects/{project_id}/trigger")
async def trigger_project(
    project_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Kick off a digest run for this project immediately."""
    row = await repo._pool.fetchrow(
        "SELECT * FROM research_projects WHERE id = $1", project_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="project not found")
    await _assert_workspace_access(user_id, row["workspace_id"], repo)

    project = dict(row)
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

        result = await run_research_digest(
            workspace_id=str(project["workspace_id"]),
            config=config,
        )
        await repo._pool.execute(
            "UPDATE research_projects SET last_run_at = now() WHERE id = $1", project_id
        )
        persisted = len(result.get("persisted_ids", [])) if isinstance(result, dict) else 0
        return {"status": "ok", "papers_processed": persisted}
    except Exception as exc:
        logger.warning("project.trigger.failed", exc_info=True, project_id=str(project_id))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
