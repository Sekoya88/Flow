from __future__ import annotations

import inspect
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from flow.infrastructure.auth.jwt_utils import (
    create_access_token,
    create_stream_token,
    decode_stream_token,
)
from flow.interfaces.http.deps import get_stream_sse_user

_SECRET = "test-secret-at-least-32-chars-long!!"


def _settings():
    return SimpleNamespace(jwt_secret=_SECRET)


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def _call(execution_id, *, creds=None, stream_jwt=None):
    return await get_stream_sse_user(
        execution_id=execution_id,
        creds=creds,
        settings=_settings(),
        stream_jwt=stream_jwt,
    )


def test_stream_token_roundtrip() -> None:
    secret = "test-secret-at-least-32-chars-long!!"
    uid = uuid4()
    eid = uuid4()
    tok = create_stream_token(secret=secret, sub=uid, execution_id=eid, ttl_seconds=60)
    u2, e2 = decode_stream_token(secret, tok)
    assert u2 == uid
    assert e2 == eid


def test_access_token_rejected_for_stream_decode() -> None:
    secret = "test-secret-at-least-32-chars-long!!"
    access = create_access_token(secret=secret, sub=uuid4())
    with pytest.raises(ValueError, match="wrong token type"):
        decode_stream_token(secret, access)


def test_stream_token_bad_secret() -> None:
    tok = create_stream_token(secret="a" * 32, sub=uuid4(), execution_id=uuid4())
    with pytest.raises(ValueError):
        decode_stream_token("b" * 32, tok)


# ── get_stream_sse_user dependency ──────────────────────────────────────────


def test_no_access_token_query_param_accepted() -> None:
    """Regression: the legacy full-scope `access_token` query param was removed."""
    params = inspect.signature(get_stream_sse_user).parameters
    assert "access_token" not in params
    assert "stream_jwt" in params


@pytest.mark.asyncio
async def test_scoped_stream_jwt_authorizes() -> None:
    uid, eid = uuid4(), uuid4()
    tok = create_stream_token(secret=_SECRET, sub=uid, execution_id=eid)
    assert await _call(eid, stream_jwt=tok) == uid


@pytest.mark.asyncio
async def test_stream_jwt_for_other_execution_is_forbidden() -> None:
    uid, eid = uuid4(), uuid4()
    tok = create_stream_token(secret=_SECRET, sub=uid, execution_id=eid)
    with pytest.raises(HTTPException) as exc:
        await _call(uuid4(), stream_jwt=tok)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_bearer_header_authorizes_non_browser_clients() -> None:
    uid, eid = uuid4(), uuid4()
    tok = create_access_token(secret=_SECRET, sub=uid)
    assert await _call(eid, creds=_bearer(tok)) == uid


@pytest.mark.asyncio
async def test_missing_credentials_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        await _call(uuid4())
    assert exc.value.status_code == 401
