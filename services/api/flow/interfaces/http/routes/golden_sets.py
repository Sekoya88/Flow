"""Golden sets CRUD + evaluation API."""
from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from flow.application.golden_evaluator import evaluate_golden_set
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo

router = APIRouter(prefix="/api/v1/golden-sets", tags=["golden-sets"])


# ── Schemas ──────────────────────────────────────────────────────────

class CreateSetBody(BaseModel):
    name: str
    description: str = ""


class CreateItemBody(BaseModel):
    input_text: str
    expected_output: str
    scoring_criteria: str = ""


class EvaluateBody(BaseModel):
    agent_id: UUID
    agent_version_label: str = ""


# ── Helpers ──────────────────────────────────────────────────────────

async def _get_workspace(repo: FlowRepository, user_id: UUID) -> UUID:
    ws = await repo.list_workspaces_for_user(user_id)
    if not ws:
        raise HTTPException(status_code=404, detail="no workspace")
    return ws[0]["id"]


async def _assert_set_access(pool, set_id: UUID, workspace_id: UUID):
    row = await pool.fetchrow(
        "SELECT id FROM golden_sets WHERE id=$1 AND workspace_id=$2",
        set_id, workspace_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="golden set not found")


# ── Routes ───────────────────────────────────────────────────────────

@router.post("")
async def create_golden_set(
    body: CreateSetBody,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws_id = await _get_workspace(repo, user_id)
    sid = await repo._pool.fetchval(
        "INSERT INTO golden_sets (workspace_id, name, description) VALUES ($1,$2,$3) RETURNING id",
        ws_id, body.name.strip(), body.description.strip(),
    )
    return {"id": str(sid), "name": body.name.strip()}


@router.get("")
async def list_golden_sets(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws_id = await _get_workspace(repo, user_id)
    rows = await repo._pool.fetch(
        """
        SELECT gs.id, gs.name, gs.description, gs.created_at,
               COUNT(gi.id)::int AS item_count
        FROM golden_sets gs
        LEFT JOIN golden_items gi ON gi.set_id = gs.id
        WHERE gs.workspace_id = $1
        GROUP BY gs.id
        ORDER BY gs.created_at DESC
        """,
        ws_id,
    )
    return {
        "sets": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "description": r["description"],
                "item_count": r["item_count"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


@router.get("/{set_id}")
async def get_golden_set(
    set_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws_id = await _get_workspace(repo, user_id)
    await _assert_set_access(repo._pool, set_id, ws_id)
    items = await repo._pool.fetch(
        "SELECT id, input_text, expected_output, scoring_criteria, created_at FROM golden_items WHERE set_id=$1 ORDER BY created_at",
        set_id,
    )
    return {
        "items": [
            {
                "id": str(r["id"]),
                "input_text": r["input_text"],
                "expected_output": r["expected_output"],
                "scoring_criteria": r["scoring_criteria"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in items
        ]
    }


@router.post("/{set_id}/items")
async def add_golden_item(
    set_id: UUID,
    body: CreateItemBody,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws_id = await _get_workspace(repo, user_id)
    await _assert_set_access(repo._pool, set_id, ws_id)
    iid = await repo._pool.fetchval(
        """
        INSERT INTO golden_items (set_id, input_text, expected_output, scoring_criteria)
        VALUES ($1,$2,$3,$4) RETURNING id
        """,
        set_id, body.input_text.strip(), body.expected_output.strip(), body.scoring_criteria.strip(),
    )
    return {"id": str(iid)}


@router.delete("/{set_id}/items/{item_id}")
async def delete_golden_item(
    set_id: UUID,
    item_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws_id = await _get_workspace(repo, user_id)
    await _assert_set_access(repo._pool, set_id, ws_id)
    await repo._pool.execute("DELETE FROM golden_items WHERE id=$1 AND set_id=$2", item_id, set_id)
    return {"ok": True}


@router.get("/{set_id}/results")
async def get_results(
    set_id: UUID,
    agent_id: UUID | None = None,
    user_id: Annotated[UUID, Depends(get_current_user_id)] = None,
    repo: Annotated[FlowRepository, Depends(get_repo)] = None,
) -> dict:
    ws_id = await _get_workspace(repo, user_id)  # type: ignore
    await _assert_set_access(repo._pool, set_id, ws_id)  # type: ignore

    filter_sql = "AND gr.agent_id = $3" if agent_id else ""
    params = [set_id, ws_id] + ([agent_id] if agent_id else [])

    rows = await repo._pool.fetch(  # type: ignore
        f"""
        SELECT gr.id, gr.item_id, gr.agent_id, gr.agent_version_label,
               gr.score, gr.grading_rationale, gr.actual_output, gr.created_at,
               gi.input_text, gi.expected_output
        FROM golden_results gr
        JOIN golden_items gi ON gi.id = gr.item_id
        WHERE gi.set_id = $1 {filter_sql}
        ORDER BY gr.created_at DESC
        LIMIT 200
        """,
        *params,
    )

    items_rows = [{
        "id": str(r["id"]),
        "item_id": str(r["item_id"]),
        "agent_id": str(r["agent_id"]),
        "agent_version_label": r["agent_version_label"],
        "score": r["score"],
        "rationale": r["grading_rationale"],
        "actual_output": r["actual_output"],
        "input_text": r["input_text"],
        "expected_output": r["expected_output"],
        "created_at": r["created_at"].isoformat(),
    } for r in rows]

    scores = [r["score"] for r in rows if r["score"] is not None]
    return {
        "results": items_rows,
        "aggregate": {
            "count": len(scores),
            "avg_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
            "pass_rate": round(len([s for s in scores if s >= 0.7]) / len(scores), 3) if scores else 0.0,
            "min_score": round(min(scores), 3) if scores else 0.0,
        },
    }


@router.post("/{set_id}/evaluate")
async def trigger_evaluate(
    set_id: UUID,
    body: EvaluateBody,
    background_tasks: BackgroundTasks,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Evaluate a golden set against an agent asynchronously."""
    ws_id = await _get_workspace(repo, user_id)
    await _assert_set_access(repo._pool, set_id, ws_id)

    async def _run():
        await evaluate_golden_set(
            repo._pool,
            set_id,
            body.agent_id,
            body.agent_version_label or None,
            workspace_id=ws_id,
            user_id=user_id,
        )

    background_tasks.add_task(_run)
    return {"status": "evaluating", "set_id": str(set_id), "agent_id": str(body.agent_id)}
