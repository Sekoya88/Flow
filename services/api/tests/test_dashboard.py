"""Integration tests for /api/v1/dashboard routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from flow.infrastructure.auth.jwt_utils import create_access_token
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_repo
from flow.interfaces.http.main import create_app

_SECRET = "b" * 32
_USER_ID = uuid4()

_COUNTS = {
    "agents": 3,
    "executions": 42,
    "schedules": 2,
    "golden_sets": 5,
}


def _auth() -> dict:
    token = create_access_token(secret=_SECRET, sub=_USER_ID)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLOW_JWT_SECRET", _SECRET)
    from flow import config as cfg

    cfg.get_settings.cache_clear()

    _app = create_app()
    repo = MagicMock(spec=FlowRepository)
    repo.dashboard_counts = AsyncMock(return_value=_COUNTS)
    _app.dependency_overrides[get_repo] = lambda: repo
    return _app


@pytest.mark.asyncio
async def test_dashboard_summary_returns_counts(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/dashboard/summary", headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert data["agents"] == 3
    assert data["executions"] == 42


@pytest.mark.asyncio
async def test_dashboard_summary_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/v1/dashboard/summary")
    assert r.status_code == 401
