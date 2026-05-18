"""SOUL.md persona routes — read / save / regenerate per (workspace, user)."""
from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from flow.application.persona_service import regenerate_persona, synthesize_from_questionnaire
from flow.config import Settings, get_settings
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_pool, get_repo, get_settings_dep

router = APIRouter(prefix="/api/v1/personas", tags=["personas"])


class PersonaSaveIn(BaseModel):
    workspace_id: UUID
    content_md: str = Field(..., max_length=20_000)


class PersonaRegenerateIn(BaseModel):
    workspace_id: UUID


class QuestionnaireAnswer(BaseModel):
    question: str
    answer: str


class PersonaQuestionnaireIn(BaseModel):
    workspace_id: UUID
    answers: list[QuestionnaireAnswer]


def _row_to_out(row: dict | None) -> dict | None:
    if row is None:
        return None
    df = row["derived_from"]
    if isinstance(df, str):
        try:
            df = json.loads(df)
        except json.JSONDecodeError:
            df = {}
    return {
        "id": str(row["id"]),
        "workspace_id": str(row["workspace_id"]),
        "user_id": str(row["user_id"]),
        "content_md": row["content_md"],
        "version": row["version"],
        "derived_from": df,
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


async def _assert_workspace_access(repo: FlowRepository, user_id: UUID, workspace_id: UUID) -> None:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if workspace_id not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="workspace access denied")


@router.get("/me")
async def get_my_persona(
    workspace_id: Annotated[UUID, Query()],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> dict:
    await _assert_workspace_access(repo, user_id, workspace_id)
    row = await pool.fetchrow(
        """
        SELECT id, workspace_id, user_id, content_md, version, derived_from, created_at, updated_at
        FROM user_personas
        WHERE workspace_id = $1 AND user_id = $2
        """,
        workspace_id,
        user_id,
    )
    return {"persona": _row_to_out(dict(row) if row else None)}


@router.put("/me")
async def save_my_persona(
    body: PersonaSaveIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> dict:
    await _assert_workspace_access(repo, user_id, body.workspace_id)
    derived = {"manual": True}
    row = await pool.fetchrow(
        """
        INSERT INTO user_personas (workspace_id, user_id, content_md, version, derived_from)
        VALUES ($1, $2, $3, 1, $4::jsonb)
        ON CONFLICT (workspace_id, user_id) DO UPDATE
        SET content_md = EXCLUDED.content_md,
            version = user_personas.version + 1,
            derived_from = user_personas.derived_from || EXCLUDED.derived_from,
            updated_at = now()
        RETURNING id, workspace_id, user_id, content_md, version, derived_from, created_at, updated_at
        """,
        body.workspace_id,
        user_id,
        body.content_md,
        json.dumps(derived),
    )
    assert row is not None
    return {"persona": _row_to_out(dict(row))}


@router.post("/me/questionnaire")
async def questionnaire_persona(
    body: PersonaQuestionnaireIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> dict:
    await _assert_workspace_access(repo, user_id, body.workspace_id)
    from flow.application.persona_service import _build_persona_llm
    llm = _build_persona_llm(settings)
    answers = [{"question": a.question, "answer": a.answer} for a in body.answers]
    content = await synthesize_from_questionnaire(llm, answers)
    derived = {"questionnaire": True, "llm": llm is not None, "manual": False}
    row = await pool.fetchrow(
        """
        INSERT INTO user_personas (workspace_id, user_id, content_md, version, derived_from)
        VALUES ($1, $2, $3, 1, $4::jsonb)
        ON CONFLICT (workspace_id, user_id) DO UPDATE
        SET content_md = EXCLUDED.content_md,
            version = user_personas.version + 1,
            derived_from = EXCLUDED.derived_from,
            updated_at = now()
        RETURNING id, workspace_id, user_id, content_md, version, derived_from, created_at, updated_at
        """,
        body.workspace_id,
        user_id,
        content,
        json.dumps(derived),
    )
    assert row is not None
    return {"persona": _row_to_out(dict(row))}


@router.post("/me/regenerate")
async def regenerate_my_persona(
    body: PersonaRegenerateIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> dict:
    await _assert_workspace_access(repo, user_id, body.workspace_id)
    row = await regenerate_persona(pool, body.workspace_id, user_id, settings)
    return {"persona": _row_to_out(row)}
