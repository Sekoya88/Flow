"""Tests for /api/v1/digest routes."""
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
_PAPER_ID = uuid4()


def _auth() -> dict:
    return {"Authorization": f"Bearer {create_access_token(secret=_SECRET, sub=_USER_ID)}"}


def _make_config_row(**overrides) -> dict:
    base = {
        "id": uuid4(),
        "workspace_id": _WS_ID,
        "enabled": False,
        "schedule_hour": 8,
        "min_relevance_score": 0.5,
        "arxiv_categories": ["cs.AI", "cs.LG"],
        "custom_sources": [],
        "obsidian_mode": "filesystem",
        "obsidian_vault_path": None,
        "obsidian_api_url": None,
        "obsidian_cloud_bucket": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": None,
    }
    return {**base, **overrides}


def _make_paper_row(**overrides) -> dict:
    base = {
        "id": _PAPER_ID,
        "workspace_id": _WS_ID,
        "title": "Test Paper",
        "abstract": "An abstract.",
        "source_url": "https://arxiv.org/abs/2501.00001",
        "arxiv_id": "2501.00001",
        "authors": ["Alice", "Bob"],
        "categories": ["cs.AI"],
        "relevance_score": 0.8,
        "tldr": "A short summary.",
        "key_insights": "Key point.",
        "summary_md": None,
        "obsidian_path": None,
        "status": "unread",
        "published_at": None,
        "digested_at": "2026-01-01T00:00:00Z",
    }
    return {**base, **overrides}


def _make_repo(config=None, papers=None) -> FlowRepository:
    repo = MagicMock(spec=FlowRepository)
    repo.list_workspaces_for_user = AsyncMock(return_value=[{"id": _WS_ID}])
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=config if config is not None else _make_config_row())
    pool.fetch = AsyncMock(return_value=papers if papers is not None else [_make_paper_row()])
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
async def test_get_digest_config(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/v1/digest/config?workspace_id={_WS_ID}", headers=_auth())
    assert r.status_code == 200
    assert r.json()["schedule_hour"] == 8


@pytest.mark.asyncio
async def test_get_digest_config_not_configured(app):
    repo = _make_repo()
    repo.pool.fetchrow = AsyncMock(return_value=None)
    app.dependency_overrides[get_repo] = lambda: repo
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/v1/digest/config?workspace_id={_WS_ID}", headers=_auth())
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_upsert_digest_config(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.put(
            "/api/v1/digest/config",
            json={
                "workspace_id": str(_WS_ID),
                "enabled": True,
                "schedule_hour": 7,
                "min_relevance_score": 0.6,
                "arxiv_categories": ["cs.AI"],
            },
            headers=_auth(),
        )
    assert r.status_code == 200
    assert r.json()["enabled"] is False


@pytest.mark.asyncio
async def test_list_papers(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/v1/digest/papers?workspace_id={_WS_ID}", headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["title"] == "Test Paper"


@pytest.mark.asyncio
async def test_list_papers_empty(app):
    repo = _make_repo(papers=[])
    app.dependency_overrides[get_repo] = lambda: repo
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/v1/digest/papers?workspace_id={_WS_ID}", headers=_auth())
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_patch_paper_status(app):
    repo = _make_repo()
    repo.pool.fetchrow = AsyncMock(
        side_effect=[
            {"workspace_id": _WS_ID},
            _make_paper_row(status="read"),
        ]
    )
    app.dependency_overrides[get_repo] = lambda: repo
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.patch(
            f"/api/v1/digest/papers/{_PAPER_ID}",
            json={"status": "read"},
            headers=_auth(),
        )
    assert r.status_code == 200
    assert r.json()["status"] == "read"


@pytest.mark.asyncio
async def test_patch_paper_not_found(app):
    repo = _make_repo()
    repo.pool.fetchrow = AsyncMock(return_value=None)
    app.dependency_overrides[get_repo] = lambda: repo
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.patch(
            f"/api/v1/digest/papers/{uuid4()}",
            json={"status": "read"},
            headers=_auth(),
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_run_digest_queues_job(app):
    with patch("flow.infrastructure.queue.client.get_arq_pool") as mock_pool:
        mock_arq = AsyncMock()
        mock_arq.enqueue_job = AsyncMock(return_value=MagicMock(job_id="job-123"))
        mock_pool.return_value = mock_arq
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/api/v1/digest/run",
                json={"workspace_id": str(_WS_ID)},
                headers=_auth(),
            )
    assert r.status_code == 202
    assert r.json()["job_id"] == "job-123"
    assert r.json()["status"] == "queued"
