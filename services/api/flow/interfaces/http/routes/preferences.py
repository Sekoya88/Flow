from __future__ import annotations

import io
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from flow.application.preference_service import (
    effective_score,
    auto_graduate,
    extract_preferences_from_cv,
    process_onboarding_answers,
)
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo
from flow.interfaces.http.schemas import (
    OnboardingAnswersIn,
    PreferenceCreateIn,
    PreferencePatchIn,
)

router = APIRouter(prefix="/api/v1/preferences", tags=["preferences"])

_MAX_CV_BYTES = 5 * 1024 * 1024  # 5 MB


def _row_to_out(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "class": row["class"],
        "value": row["value"],
        "score": effective_score(
            row["score"],
            row["last_reinforced_at"],
            row["decay_half_life_days"],
            row.get("pinned", False),
        ),
        "status": row["status"],
        "pinned": row["pinned"],
        "agent_id": str(row["agent_id"]) if row["agent_id"] else None,
        "last_reinforced_at": row["last_reinforced_at"].isoformat(),
        "created_at": row["created_at"].isoformat(),
    }


async def _assert_workspace_access(repo: FlowRepository, user_id: UUID, workspace_id: UUID) -> None:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if workspace_id not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="workspace access denied")


@router.get("")
async def list_preferences(
    workspace_id: UUID,
    agent_id: UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
    class_filter: str | None = Query(None, alias="class"),
    user_id: Annotated[UUID, Depends(get_current_user_id)] = ...,
    repo: Annotated[FlowRepository, Depends(get_repo)] = ...,
) -> dict:
    await _assert_workspace_access(repo, user_id, workspace_id)
    global_rows, agent_rows = await repo.get_typed_preferences(
        workspace_id, user_id, agent_id, status_filter, class_filter
    )
    return {
        "global": [_row_to_out(dict(r)) for r in global_rows],
        "agent_specific": [_row_to_out(dict(r)) for r in agent_rows],
    }


@router.get("/onboarding-status")
async def onboarding_status(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)] = ...,
    repo: Annotated[FlowRepository, Depends(get_repo)] = ...,
) -> dict:
    await _assert_workspace_access(repo, user_id, workspace_id)
    return await repo.get_onboarding_status(workspace_id, user_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_preference(
    body: PreferenceCreateIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)] = ...,
    repo: Annotated[FlowRepository, Depends(get_repo)] = ...,
) -> dict:
    await _assert_workspace_access(repo, user_id, body.workspace_id)
    row = await repo.upsert_typed_preference(
        body.workspace_id, user_id, body.class_, body.value,
        body.agent_id, initial_status=body.status,
    )
    new_status = auto_graduate(dict(row))
    if new_status:
        await repo.apply_preference_graduation(row["id"], new_status)
        row = await repo.get_preference_by_id(row["id"], user_id)
    return _row_to_out(dict(row))


@router.patch("/{pref_id}")
async def patch_preference(
    pref_id: UUID,
    body: PreferencePatchIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)] = ...,
    repo: Annotated[FlowRepository, Depends(get_repo)] = ...,
) -> dict:
    valid_actions = {"promote", "pin", "unpin", "forget", "veto"}
    if body.action not in valid_actions:
        raise HTTPException(status_code=422, detail=f"action must be one of {valid_actions}")
    row = await repo.patch_typed_preference(pref_id, user_id, body.action)
    if row is None:
        return {"deleted": True}
    return _row_to_out(dict(row))


@router.delete("/{pref_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preference(
    pref_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)] = ...,
    repo: Annotated[FlowRepository, Depends(get_repo)] = ...,
) -> None:
    deleted = await repo.delete_typed_preference(pref_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="preference not found")


@router.post("/onboarding")
async def submit_onboarding(
    workspace_id: UUID,
    body: OnboardingAnswersIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)] = ...,
    repo: Annotated[FlowRepository, Depends(get_repo)] = ...,
) -> dict:
    await _assert_workspace_access(repo, user_id, workspace_id)
    raw_answers = [{"class": a.class_, "value": a.value} for a in body.answers]
    processed = process_onboarding_answers(raw_answers)
    count = 0
    for item in processed:
        await repo.upsert_typed_preference(
            workspace_id, user_id, item["class"], item["value"],
            initial_status="active",
        )
        count += 1
    return {"created": count}


@router.post("/import-cv")
async def import_cv(
    workspace_id: UUID,
    file: UploadFile = File(...),
    user_id: Annotated[UUID, Depends(get_current_user_id)] = ...,
    repo: Annotated[FlowRepository, Depends(get_repo)] = ...,
) -> dict:
    await _assert_workspace_access(repo, user_id, workspace_id)

    is_pdf = (file.content_type or "") == "application/pdf" or (file.filename or "").endswith(".pdf")
    is_docx = (
        (file.content_type or "") == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or (file.filename or "").endswith(".docx")
    )
    if not is_pdf and not is_docx:
        raise HTTPException(status_code=422, detail="file must be PDF or DOCX")

    raw = await file.read()
    if len(raw) > _MAX_CV_BYTES:
        raise HTTPException(status_code=413, detail="file exceeds 5 MB limit")

    if is_pdf:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(raw))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        import docx
        doc = docx.Document(io.BytesIO(raw))
        text = "\n".join(p.text for p in doc.paragraphs)

    from flow.config import get_settings
    from langchain_anthropic import ChatAnthropic
    settings = get_settings()
    llm = ChatAnthropic(model="claude-haiku-4-5-20251001", api_key=settings.anthropic_api_key)

    prefs = await extract_preferences_from_cv(llm, text)

    for item in prefs:
        await repo.upsert_typed_preference(
            workspace_id, user_id, item["class"], item["value"],
            initial_status="active",
        )

    return {"extracted": len(prefs), "preview": prefs}
