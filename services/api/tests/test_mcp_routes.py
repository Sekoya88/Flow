"""Tests for /api/v1/mcp routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
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
_SERVER_ID = uuid4()


def _auth() -> dict:
    return {"Authorization": f"Bearer {create_access_token(secret=_SECRET, sub=_USER_ID)}"}


def _make_server_row(**overrides) -> dict:
    base = {
        "id": _SERVER_ID,
        "workspace_id": _WS_ID,
        "name": "Test MCP",
        "url": "http://localhost:18001/sse",
        "transport": "sse",
        "active": True,
        "metadata": {},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": None,
    }
    return {**base, **overrides}


def _make_repo(server_row=None) -> FlowRepository:
    repo = MagicMock(spec=FlowRepository)
    repo.list_workspaces_for_user = AsyncMock(return_value=[{"id": _WS_ID}])

    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=[server_row or _make_server_row()])
    pool.fetchrow = AsyncMock(return_value=server_row or _make_server_row())
    pool.execute = AsyncMock()
    repo.pool = pool
    return repo


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLOW_JWT_SECRET", _SECRET)
    from flow import config as cfg
    cfg.get_settings.cache_clear()
    _app = create_app()
    _app.dependency_overrides[get_repo] = lambda: _make_repo()
    return _app


@pytest.mark.asyncio
async def test_list_mcp_servers_empty(app):
    app.dependency_overrides[get_repo] = lambda: (
        r := _make_repo(),
        setattr(r.pool, "fetch", AsyncMock(return_value=[])),
        r
    )[-1]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/v1/mcp/servers?workspace_id={_WS_ID}", headers=_auth())
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_mcp_servers_returns_rows(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/v1/mcp/servers?workspace_id={_WS_ID}", headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test MCP"


@pytest.mark.asyncio
async def test_create_mcp_server(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/mcp/servers",
            json={"workspace_id": str(_WS_ID), "name": "My MCP", "url": "http://mcp/sse"},
            headers=_auth(),
        )
    assert r.status_code == 201
    assert r.json()["name"] == "Test MCP"


@pytest.mark.asyncio
async def test_delete_mcp_server(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.delete(f"/api/v1/mcp/servers/{_SERVER_ID}", headers=_auth())
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_mcp_server_not_found(app):
    app.dependency_overrides[get_repo] = lambda: (
        r := _make_repo(server_row=None),
        setattr(r.pool, "fetchrow", AsyncMock(return_value=None)),
        r
    )[-1]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.delete(f"/api/v1/mcp/servers/{uuid4()}", headers=_auth())
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_workspace_forbidden(app):
    repo = _make_repo()
    repo.list_workspaces_for_user = AsyncMock(return_value=[])
    app.dependency_overrides[get_repo] = lambda: repo
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/v1/mcp/servers?workspace_id={_WS_ID}", headers=_auth())
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_ping_mcp_server(app):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MagicMock(status_code=200)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(f"/api/v1/mcp/servers/{_SERVER_ID}/ping", headers=_auth())
    assert r.status_code == 200
