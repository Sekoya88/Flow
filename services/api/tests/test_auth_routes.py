"""Integration tests for auth routes: register, login, /me, duplicate email, invalid credentials."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from flow.infrastructure.auth.jwt_utils import create_access_token
from flow.infrastructure.auth.password import hash_password
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_repo
from flow.interfaces.http.main import create_app

_SECRET = "s" * 32
_USER_ID = uuid4()
_WS_ID = uuid4()


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLOW_JWT_SECRET", _SECRET)
    from flow import config as cfg

    cfg.get_settings.cache_clear()
    _app = create_app()
    repo = MagicMock(spec=FlowRepository)
    _app.dependency_overrides[get_repo] = lambda: repo
    _app.state._repo = repo
    return _app


def _auth(user_id=None) -> dict:
    return {"Authorization": f"Bearer {create_access_token(secret=_SECRET, sub=user_id or _USER_ID)}"}


# ── POST /register ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_creates_user_and_returns_token(app):
    repo: MagicMock = app.state._repo
    repo.get_user_by_email = AsyncMock(return_value=None)
    repo.create_user = AsyncMock(return_value=_USER_ID)
    repo.create_workspace = AsyncMock(return_value=_WS_ID)
    repo.add_workspace_member = AsyncMock()
    # Patch seed so we don't need a real pool
    repo._pool = MagicMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/auth/register", json={"email": "a@b.com", "password": "secret123"})

    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert len(body["access_token"]) > 20


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(app):
    repo: MagicMock = app.state._repo
    repo.get_user_by_email = AsyncMock(return_value={"id": _USER_ID})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/auth/register", json={"email": "dup@b.com", "password": "secret123"})

    assert r.status_code == 409
    assert "email taken" in r.json()["detail"]


# ── POST /login ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_valid_credentials_returns_token(app):
    repo: MagicMock = app.state._repo
    repo.get_user_by_email = AsyncMock(return_value={
        "id": _USER_ID,
        "password_hash": hash_password("secret123"),
    })

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/auth/login", json={"email": "a@b.com", "password": "secret123"})

    assert r.status_code == 200
    assert "access_token" in r.json()


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(app):
    repo: MagicMock = app.state._repo
    repo.get_user_by_email = AsyncMock(return_value={
        "id": _USER_ID,
        "password_hash": hash_password("correct"),
    })

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/auth/login", json={"email": "a@b.com", "password": "wrong"})

    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(app):
    repo: MagicMock = app.state._repo
    repo.get_user_by_email = AsyncMock(return_value=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/auth/login", json={"email": "ghost@x.com", "password": "any"})

    assert r.status_code == 401


# ── GET /me ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_me_returns_user_and_workspaces(app):
    repo: MagicMock = app.state._repo
    repo.get_user = AsyncMock(return_value={"id": _USER_ID, "email": "a@b.com"})
    repo.list_workspaces_for_user = AsyncMock(return_value=[
        {"id": _WS_ID, "name": "Personal", "role": "admin"},
    ])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/auth/me", headers=_auth())

    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "a@b.com"
    assert len(body["workspaces"]) == 1
    assert body["workspaces"][0]["name"] == "Personal"


@pytest.mark.asyncio
async def test_me_returns_401_without_token(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/auth/me")

    assert r.status_code == 401
