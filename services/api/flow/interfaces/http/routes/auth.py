from __future__ import annotations

import asyncio
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from flow.config import Settings, get_settings
from flow.infrastructure.auth.jwt_utils import create_access_token
from flow.infrastructure.auth.password import hash_password, verify_password
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo
from flow.interfaces.http.schemas import ChangePasswordIn, LoginIn, RegisterIn, TokenOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
async def register(
    body: RegisterIn,
    repo: Annotated[FlowRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenOut:
    existing = await repo.get_user_by_email(body.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email taken")
    uid = await repo.create_user(body.email, hash_password(body.password))
    ws = await repo.create_workspace("Personal")
    await repo.add_workspace_member(ws, uid, "admin")
    token = create_access_token(secret=settings.jwt_secret, sub=uid)

    # Seed canonical agents + golden sets in background so registration returns immediately
    async def _seed():
        from scripts.seed_agents_and_datasets import seed_workspace
        try:
            await seed_workspace(repo._pool, ws)
        except Exception:
            logger.exception("Failed to seed workspace %s for new user", ws)

    asyncio.ensure_future(_seed())

    return TokenOut(access_token=token)


@router.post("/login", response_model=TokenOut)
async def login(
    body: LoginIn,
    repo: Annotated[FlowRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenOut:
    row = await repo.get_user_by_email(body.email)
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    token = create_access_token(secret=settings.jwt_secret, sub=row["id"])
    return TokenOut(access_token=token)


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> None:
    row = await repo.get_user(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="user not found")
    full = await repo.get_user_by_email(row["email"])
    if not full or not verify_password(body.current_password, full["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="current password incorrect")
    await repo._pool.execute(
        "UPDATE users SET password_hash = $1 WHERE id = $2",
        hash_password(body.new_password),
        user_id,
    )


@router.get("/me")
async def me(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    user = await repo.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    workspaces = await repo.list_workspaces_for_user(user_id)
    return {
        "user": {"id": str(user["id"]), "email": user["email"]},
        "workspaces": [
            {"id": str(w["id"]), "name": w["name"], "role": w["role"]} for w in workspaces
        ],
    }
