"""Contract tests for PATCH /api/v1/preferences/{id} (JSON body + auth)."""

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

_SECRET = "d" * 32
_USER_ID = uuid4()
_PREF_ID = uuid4()


def _auth() -> dict:
    token = create_access_token(secret=_SECRET, sub=_USER_ID)
    return {"Authorization": f"Bearer {token}"}


def _make_repo() -> FlowRepository:
    ts = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)
    row = {
        "id": _PREF_ID,
        "class": "tooling",
        "value": "Python",
        "score": 0.6,
        "status": "active",
        "pinned": False,
        "agent_id": None,
        "last_reinforced_at": ts,
        "decay_half_life_days": 30,
        "created_at": ts,
    }
    repo = MagicMock(spec=FlowRepository)
    repo.patch_typed_preference = AsyncMock(return_value=row)
    return repo


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLOW_JWT_SECRET", _SECRET)
    from flow import config as cfg

    cfg.get_settings.cache_clear()
    _app = create_app()
    _app.dependency_overrides[get_repo] = _make_repo
    return _app


@pytest.mark.asyncio
async def test_patch_preference_accepts_json_body(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.patch(
            f"/api/v1/preferences/{_PREF_ID}",
            headers={**_auth(), "Content-Type": "application/json"},
            json={"action": "promote"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["class"] == "tooling"
    assert data["value"] == "Python"


@pytest.mark.asyncio
async def test_patch_preference_missing_action_returns_422(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.patch(
            f"/api/v1/preferences/{_PREF_ID}",
            headers=_auth(),
            content=b"not-json",
        )
    assert r.status_code == 422
