from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from flow.config import Settings, get_settings
from flow.infrastructure.auth.jwt_utils import create_access_token
from flow.infrastructure.auth.password import hash_password, verify_password
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo
from flow.interfaces.http.schemas import LoginIn, RegisterIn, TokenOut

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
            pass  # non-fatal — user can still use the app

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
