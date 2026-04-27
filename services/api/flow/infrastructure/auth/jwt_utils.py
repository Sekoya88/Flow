from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import JWTError, jwt


def create_access_token(*, secret: str, sub: UUID, expires_hours: int = 24) -> str:
    now = datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "sub": str(sub),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=expires_hours)).timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(secret: str, token: str) -> UUID:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        sub = payload.get("sub")
        if not sub:
            raise JWTError("missing sub")
        return UUID(str(sub))
    except JWTError as exc:
        raise ValueError("invalid token") from exc


def create_stream_token(
    *, secret: str, sub: UUID, execution_id: UUID, ttl_seconds: int = 120
) -> str:
    """Short-lived JWT for browser SSE (EventSource cannot send Authorization)."""
    now = datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "sub": str(sub),
        "exec": str(execution_id),
        "typ": "sse_stream",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_stream_token(secret: str, token: str) -> tuple[UUID, UUID]:
    """Returns (user_id, execution_id). Raises ValueError on bad token or wrong type."""
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError("invalid stream token") from exc
    if payload.get("typ") != "sse_stream":
        raise ValueError("wrong token type")
    sub = payload.get("sub")
    exec_raw = payload.get("exec")
    if not sub or not exec_raw:
        raise ValueError("missing claims")
    return UUID(str(sub)), UUID(str(exec_raw))
