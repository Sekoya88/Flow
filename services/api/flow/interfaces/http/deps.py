from __future__ import annotations

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from flow.config import Settings, get_settings
from flow.infrastructure.auth.jwt_utils import decode_stream_token, decode_token
from flow.infrastructure.persistence.repo import FlowRepository

_bearer = HTTPBearer(auto_error=False)


async def get_pool(request: Request) -> asyncpg.Pool:
    pool = request.app.state.pool
    if pool is None:
        raise HTTPException(status_code=500, detail="db not configured")
    return pool


def get_settings_dep() -> Settings:
    return get_settings()


async def get_current_user_id(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> UUID:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token")
    try:
        return decode_token(settings.jwt_secret, creds.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc


async def get_repo(pool: Annotated[asyncpg.Pool, Depends(get_pool)]) -> FlowRepository:
    return FlowRepository(pool)


async def get_stream_sse_user(
    execution_id: UUID,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    stream_jwt: Annotated[str | None, Query(description="From POST /executions/{id}/stream-token")] = None,
    access_token: Annotated[str | None, Query()] = None,
) -> UUID:
    """Prefer `stream_jwt` (scoped to this execution). Fallback: Bearer or legacy `access_token` query."""
    if stream_jwt:
        try:
            uid, eid = decode_stream_token(settings.jwt_secret, stream_jwt)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid stream token"
            ) from exc
        if eid != execution_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="stream token execution mismatch"
            )
        return uid
    token: str | None = None
    if creds and creds.scheme.lower() == "bearer":
        token = creds.credentials
    elif access_token:
        token = access_token
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token")
    try:
        return decode_token(settings.jwt_secret, token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc
