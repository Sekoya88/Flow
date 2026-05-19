"""Integration tests for /api/v1/schedules routes."""
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

_SECRET = "a" * 32
_USER_ID = uuid4()
_WS_ID = uuid4()
_AGENT_ID = uuid4()
_SCHEDULE_ID = uuid4()


def _make_token() -> str:
    return create_access_token(secret=_SECRET, sub=_USER_ID)


def _auth() -> dict:
    return {"Authorization": f"Bearer {_make_token()}"}


def _make_repo_mock() -> FlowRepository:
    repo = MagicMock(spec=FlowRepository)
    repo.get_agent = AsyncMock(return_value={"id": _AGENT_ID, "name": "TestAgent"})
    repo.create_agent_schedule = AsyncMock(return_value=_SCHEDULE_ID)
    repo.list_agent_schedules = AsyncMock(
        return_value=[
            {
                "id": _SCHEDULE_ID,
                "agent_id": _AGENT_ID,
                "agent_name": "TestAgent",
                "cron_expr": "0 8 * * *",
                "prompt_template": "Summarize news",
                "delivery_type": "none",
                "delivery_target": None,
                "enabled": True,
                "last_run_at": None,
                "created_at": datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC),
            }
        ]
    )
    repo.update_schedule_enabled = AsyncMock(return_value=None)
    repo.delete_agent_schedule = AsyncMock(return_value=True)
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
async def test_list_cron_jobs_returns_system_jobs(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/schedules/cron-jobs", headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert "cron_jobs" in data
    assert len(data["cron_jobs"]) == 4
    names = {j["name"] for j in data["cron_jobs"]}
    assert names == {"scheduler_tick", "auto_eval_tick", "skill_decay_tick", "persona_freshness_tick"}


@pytest.mark.asyncio
async def test_list_cron_jobs_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/schedules/cron-jobs")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_schedule_returns_id(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/schedules",
            headers=_auth(),
            json={
                "workspace_id": str(_WS_ID),
                "agent_id": str(_AGENT_ID),
                "cron_expr": "0 8 * * *",
                "prompt_template": "Summarize today's AI news",
                "delivery_type": "none",
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data["id"] == str(_SCHEDULE_ID)


@pytest.mark.asyncio
async def test_create_schedule_404_when_agent_missing(app):
    repo = _make_repo_mock()
    repo.get_agent = AsyncMock(return_value=None)
    app.dependency_overrides[get_repo] = lambda: repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/schedules",
            headers=_auth(),
            json={
                "workspace_id": str(_WS_ID),
                "agent_id": str(uuid4()),
                "delivery_type": "none",
            },
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_schedules_returns_rows(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            f"/api/v1/schedules?workspace_id={_WS_ID}",
            headers=_auth(),
        )
    assert r.status_code == 200
    data = r.json()
    assert "schedules" in data
    assert len(data["schedules"]) == 1
    assert data["schedules"][0]["cron_expr"] == "0 8 * * *"


@pytest.mark.asyncio
async def test_toggle_schedule_enabled(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.patch(
            f"/api/v1/schedules/{_SCHEDULE_ID}/toggle",
            headers=_auth(),
            json={"enabled": False},
        )
    assert r.status_code == 200
    assert r.json() == {"enabled": False}


@pytest.mark.asyncio
async def test_delete_schedule_success(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.delete(
            f"/api/v1/schedules/{_SCHEDULE_ID}?workspace_id={_WS_ID}",
            headers=_auth(),
        )
    assert r.status_code == 200
    assert r.json() == {"deleted": True}


@pytest.mark.asyncio
async def test_delete_schedule_404_when_not_found(app):
    repo = _make_repo_mock()
    repo.delete_agent_schedule = AsyncMock(return_value=False)
    app.dependency_overrides[get_repo] = lambda: repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.delete(
            f"/api/v1/schedules/{uuid4()}?workspace_id={_WS_ID}",
            headers=_auth(),
        )
    assert r.status_code == 404
