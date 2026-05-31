"""Integration tests for agents routes: create, list, patch (404), delete (404), unauthenticated."""

from __future__ import annotations

from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from flow.infrastructure.auth.jwt_utils import create_access_token
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_repo
from flow.interfaces.http.main import create_app

_SECRET = "a" * 32
_USER_ID = uuid4()
_WS_ID = uuid4()
_AGENT_ID = uuid4()


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLOW_JWT_SECRET", _SECRET)
    from flow import config as cfg

    cfg.get_settings.cache_clear()
    _app = create_app()
    repo = MagicMock(spec=FlowRepository)
    # Give repo a _pool so routes that use repo._pool don't hard-crash
    pool = MagicMock()
    pool.fetchval = AsyncMock(return_value=0)
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock()
    pool.acquire = MagicMock(return_value=_ctx_mgr())
    repo._pool = pool
    _app.dependency_overrides[get_repo] = lambda: repo
    _app.state._repo = repo
    return _app


def _ctx_mgr():
    """Async context manager that returns a MagicMock connection with transaction()."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _inner():
        conn = MagicMock()
        conn.execute = AsyncMock()
        conn.transaction = MagicMock(return_value=_tx_ctx_mgr())
        yield conn

    return _inner()


def _tx_ctx_mgr():
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _inner():
        yield

    return _inner()


def _auth() -> dict:
    return {"Authorization": f"Bearer {create_access_token(secret=_SECRET, sub=_USER_ID)}"}


def _ws_member():
    return [{"id": _WS_ID, "name": "Personal", "role": "admin"}]


def _agent_row():
    return {
        "id": _AGENT_ID,
        "name": "Alpha",
        "template": "linear-3",
        "config": {},
        "workspace_id": _WS_ID,
        "created_at": datetime.now(UTC),
    }


# ── POST /agents ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_agent_returns_id(app):
    repo: MagicMock = app.state._repo
    repo.list_workspaces_for_user = AsyncMock(return_value=_ws_member())
    repo.create_agent = AsyncMock(return_value=_AGENT_ID)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/agents",
            headers=_auth(),
            json={"workspace_id": str(_WS_ID), "name": "Test Agent", "template": "linear-3", "config": {}},
        )

    assert r.status_code == 201
    assert r.json()["id"] == str(_AGENT_ID)
    repo.create_agent.assert_awaited_once_with(_WS_ID, "Test Agent", "linear-3", {})


@pytest.mark.asyncio
async def test_create_agent_forbidden_for_non_member_workspace(app):
    repo: MagicMock = app.state._repo
    repo.list_workspaces_for_user = AsyncMock(return_value=[])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/agents",
            headers=_auth(),
            json={"workspace_id": str(_WS_ID), "name": "Spy", "template": "linear-3", "config": {}},
        )

    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_agent_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/agents",
            json={"workspace_id": str(_WS_ID), "name": "X", "template": "linear-3", "config": {}},
        )

    assert r.status_code == 401


# ── GET /workspaces/{id}/agents ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_agents_returns_agents(app):
    repo: MagicMock = app.state._repo
    repo.list_workspaces_for_user = AsyncMock(return_value=_ws_member())
    repo.list_agents = AsyncMock(return_value=[_agent_row()])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/v1/workspaces/{_WS_ID}/agents", headers=_auth())

    assert r.status_code == 200
    agents = r.json()["agents"]
    assert len(agents) == 1
    assert agents[0]["name"] == "Alpha"
    assert agents[0]["template"] == "linear-3"


@pytest.mark.asyncio
async def test_list_agents_forbidden_for_non_member_workspace(app):
    repo: MagicMock = app.state._repo
    repo.list_workspaces_for_user = AsyncMock(return_value=[])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/v1/workspaces/{uuid4()}/agents", headers=_auth())

    assert r.status_code == 403


# ── PATCH /agents/{id} — 404 path ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patch_agent_returns_404_when_not_found(app):
    repo: MagicMock = app.state._repo
    repo.list_workspaces_for_user = AsyncMock(return_value=_ws_member())
    repo.get_agent = AsyncMock(return_value=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.patch(f"/api/v1/agents/{_AGENT_ID}", headers=_auth(), json={"name": "Beta"})

    assert r.status_code == 404


# ── DELETE /agents/{id} — 404 path ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_agent_returns_404_when_not_found(app):
    repo: MagicMock = app.state._repo
    repo.list_workspaces_for_user = AsyncMock(return_value=_ws_member())
    repo.get_agent = AsyncMock(return_value=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.delete(f"/api/v1/agents/{_AGENT_ID}", headers=_auth())

    assert r.status_code == 404
