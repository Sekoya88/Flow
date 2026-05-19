"""Integration tests for /api/v1/golden-sets routes."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from flow.infrastructure.auth.jwt_utils import create_access_token
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_repo
from flow.interfaces.http.main import create_app

_SECRET = "c" * 32
_USER_ID = uuid4()
_WS_ID = uuid4()
_SET_ID = uuid4()
_ITEM_ID = uuid4()


def _auth() -> dict:
    token = create_access_token(secret=_SECRET, sub=_USER_ID)
    return {"Authorization": f"Bearer {token}"}


def _fake_record(**kw) -> dict:
    """asyncpg.Record is dict-like; MagicMock with __getitem__ works for route code."""
    m = MagicMock()
    m.__getitem__ = lambda self, k: kw[k]
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def _make_pool_mock(ws_id=_WS_ID, set_id=_SET_ID, item_id=_ITEM_ID) -> MagicMock:
    pool = MagicMock()
    ts = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)

    # _get_workspace: list_workspaces_for_user falls back to pool.fetchrow
    pool.fetchrow = AsyncMock(return_value=_fake_record(id=ws_id, name="default"))
    pool.fetchval = AsyncMock(return_value=set_id)
    pool.fetch = AsyncMock(
        return_value=[
            _fake_record(
                id=set_id,
                name="Test Set",
                description="desc",
                item_count=2,
                created_at=ts,
            )
        ]
    )
    pool.execute = AsyncMock(return_value=None)
    return pool


def _make_repo_mock(ws_id=_WS_ID) -> FlowRepository:
    pool = _make_pool_mock(ws_id=ws_id)
    repo = MagicMock(spec=FlowRepository)
    repo._pool = pool
    repo.list_workspaces_for_user = AsyncMock(return_value=[{"id": ws_id}])
    return repo


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLOW_JWT_SECRET", _SECRET)
    from flow import config as cfg

    cfg.get_settings.cache_clear()

    _app = create_app()
    repo = _make_repo_mock()
    _app.dependency_overrides[get_repo] = lambda: repo
    return _app


@pytest.mark.asyncio
async def test_list_golden_sets_returns_200(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/golden-sets", headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert "sets" in data
    assert len(data["sets"]) == 1
    assert data["sets"][0]["name"] == "Test Set"


@pytest.mark.asyncio
async def test_list_golden_sets_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/golden-sets")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_golden_set_returns_id(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/golden-sets",
            headers=_auth(),
            json={"name": "My Set", "description": "Testing"},
        )
    assert r.status_code == 200
    data = r.json()
    assert "id" in data


@pytest.mark.asyncio
async def test_get_golden_set_items(app):
    ts = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)
    repo = _make_repo_mock()
    # _assert_set_access returns the set row; fetchrow after list_workspaces
    repo._pool.fetch = AsyncMock(
        return_value=[
            _fake_record(
                id=_ITEM_ID,
                input_text="What is RAG?",
                expected_output="A technique...",
                scoring_criteria="Must mention retrieval",
                created_at=ts,
            )
        ]
    )
    # _assert_set_access uses fetchrow; keep returning the ws row for access check
    repo._pool.fetchrow = AsyncMock(return_value=_fake_record(id=_SET_ID, workspace_id=_WS_ID))
    app.dependency_overrides[get_repo] = lambda: repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/v1/golden-sets/{_SET_ID}", headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert data["items"][0]["input_text"] == "What is RAG?"


@pytest.mark.asyncio
async def test_get_golden_set_404_when_no_access(app):
    repo = _make_repo_mock()
    # _assert_set_access returns None → 404
    repo._pool.fetchrow = AsyncMock(return_value=None)
    app.dependency_overrides[get_repo] = lambda: repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/v1/golden-sets/{uuid4()}", headers=_auth())
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_add_golden_item_returns_id(app):
    repo = _make_repo_mock()
    repo._pool.fetchrow = AsyncMock(return_value=_fake_record(id=_SET_ID, workspace_id=_WS_ID))
    repo._pool.fetchval = AsyncMock(return_value=_ITEM_ID)
    app.dependency_overrides[get_repo] = lambda: repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            f"/api/v1/golden-sets/{_SET_ID}/items",
            headers=_auth(),
            json={
                "input_text": "Explain transformers",
                "expected_output": "Attention mechanism...",
                "scoring_criteria": "Must mention attention",
            },
        )
    assert r.status_code == 200
    assert r.json()["id"] == str(_ITEM_ID)


@pytest.mark.asyncio
async def test_delete_golden_item_ok(app):
    repo = _make_repo_mock()
    repo._pool.fetchrow = AsyncMock(return_value=_fake_record(id=_SET_ID, workspace_id=_WS_ID))
    app.dependency_overrides[get_repo] = lambda: repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.delete(
            f"/api/v1/golden-sets/{_SET_ID}/items/{_ITEM_ID}",
            headers=_auth(),
        )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
