"""Tests for PATCH /api/v1/skills/{skill_id} — training_mode field."""

from __future__ import annotations

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
_SKILL_ID = uuid4()


def _auth() -> dict:
    token = create_access_token(secret=_SECRET, sub=_USER_ID)
    return {"Authorization": f"Bearer {token}"}


def _make_repo_mock(patch_returns: bool = True) -> MagicMock:
    repo = MagicMock(spec=FlowRepository)
    repo.patch_skill_training_mode = AsyncMock(return_value=patch_returns)
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


# ---------------------------------------------------------------------------
# PATCH /{skill_id} — set training_mode to "react"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_skill_sets_training_mode(monkeypatch):
    """PATCH with training_mode='react' should return 200 with training_mode in response."""
    monkeypatch.setenv("FLOW_JWT_SECRET", _SECRET)
    from flow import config as cfg

    cfg.get_settings.cache_clear()

    _app = create_app()
    repo = _make_repo_mock(patch_returns=True)
    _app.dependency_overrides[get_repo] = lambda: repo

    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
        resp = await client.patch(
            f"/api/v1/skills/{_SKILL_ID}",
            json={"training_mode": "react"},
            headers=_auth(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["training_mode"] == "react"
    assert data["skill_id"] == str(_SKILL_ID)
    repo.patch_skill_training_mode.assert_awaited_once_with(_SKILL_ID, "react")


# ---------------------------------------------------------------------------
# PATCH /{skill_id} — disable training_mode with null
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_skill_disables_training_mode(monkeypatch):
    """PATCH with training_mode=null should return 200 and training_mode=null in response."""
    monkeypatch.setenv("FLOW_JWT_SECRET", _SECRET)
    from flow import config as cfg

    cfg.get_settings.cache_clear()

    _app = create_app()
    repo = _make_repo_mock(patch_returns=True)
    _app.dependency_overrides[get_repo] = lambda: repo

    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
        resp = await client.patch(
            f"/api/v1/skills/{_SKILL_ID}",
            json={"training_mode": None},
            headers=_auth(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["training_mode"] is None
    assert data["skill_id"] == str(_SKILL_ID)
    repo.patch_skill_training_mode.assert_awaited_once_with(_SKILL_ID, None)


# ---------------------------------------------------------------------------
# PATCH /{skill_id} — skill not found → 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_skill_not_found_returns_404(monkeypatch):
    """PATCH should return 404 when the repo returns False (UPDATE 0)."""
    monkeypatch.setenv("FLOW_JWT_SECRET", _SECRET)
    from flow import config as cfg

    cfg.get_settings.cache_clear()

    _app = create_app()
    repo = _make_repo_mock(patch_returns=False)
    _app.dependency_overrides[get_repo] = lambda: repo

    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as client:
        resp = await client.patch(
            f"/api/v1/skills/{_SKILL_ID}",
            json={"training_mode": "react"},
            headers=_auth(),
        )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Skill not found"
