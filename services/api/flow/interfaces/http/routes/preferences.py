from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo
from flow.interfaces.http.schemas import PreferenceUpsertIn

router = APIRouter(prefix="/api/v1/user/preferences", tags=["preferences"])


@router.get("")
async def list_prefs(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    rows = await repo.get_preferences(user_id)
    return {
        "preferences": [
            {
                "key": r["key"],
                "value": r["value"],
                "updated_at": r["updated_at"].isoformat(),
            }
            for r in rows
        ]
    }


@router.put("")
async def upsert_pref(
    body: PreferenceUpsertIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await repo.upsert_preference(user_id, body.key, body.value)
    return {"ok": True}
