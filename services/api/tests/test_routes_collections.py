"""Tests for curated collections endpoints (GET /collections, POST /collections/{id}/import)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from flow.infrastructure.auth.jwt_utils import create_access_token
from flow.infrastructure.persistence.repo import FlowRepository
from flow.infrastructure.persistence.skill_collections import CURATED_COLLECTIONS
from flow.interfaces.http.deps import get_repo
from flow.interfaces.http.main import create_app

_SECRET = "c" * 32
_USER_ID = uuid4()
_WORKSPACE_ID = uuid4()
_AGENT_ID = uuid4()


def _auth() -> dict:
    token = create_access_token(secret=_SECRET, sub=_USER_ID)
    return {"Authorization": f"Bearer {token}"}


def _make_repo_mock() -> MagicMock:
    repo = MagicMock(spec=FlowRepository)
    # list_workspaces_for_user returns a list of records with an "id" key
    repo.list_workspaces_for_user = AsyncMock(return_value=[{"id": _WORKSPACE_ID}])
    # upsert_agent_skill returns a new UUID
    repo.upsert_agent_skill = AsyncMock(return_value=uuid4())

    # _pool mock for raw SQL calls
    pool = MagicMock()
    # fetchrow for "SELECT id FROM agents WHERE workspace_id …" → returns agent row
    pool.fetchrow = AsyncMock(return_value={"id": _AGENT_ID})
    # fetch for "SELECT name FROM agent_skills …" → empty initially
    pool.fetch = AsyncMock(return_value=[])
    repo._pool = pool
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
# GET /collections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_collections(app):
    """GET /collections should return all curated collections with correct metadata."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/v1/skills/collections", headers=_auth())

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["collections"]) == len(CURATED_COLLECTIONS)
    ecc = next(col for col in body["collections"] if col["id"] == "ecc")
    assert ecc["skill_count"] == 6
    assert ecc["category"] == "Code"


# ---------------------------------------------------------------------------
# POST /collections/{collection_id}/import
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_collection_reports_per_skill_steps(monkeypatch, app):
    """Import endpoint should return per-skill step log with install/error status."""

    async def fake_fetch(repo, path):
        if "security-review" in path:
            return None  # simulate a 404 → error step
        return f"---\nname: {path.split('/')[-2]}\ndescription: d\n---\nbody"

    import flow.interfaces.http.routes.skills as mod

    monkeypatch.setattr(mod, "_fetch_raw_skill", fake_fetch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/api/v1/skills/collections/ecc/import",
            json={"workspace_id": str(_WORKSPACE_ID)},
            headers=_auth(),
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["collection_id"] == "ecc"
    assert body["installed"] >= 1
    assert any(s["status"] == "error" and "security-review" in s["path"] for s in body["steps"])


@pytest.mark.asyncio
async def test_import_collection_dedupes_on_second_run(monkeypatch, app):
    """Second import of the same collection should skip already-installed skills."""

    # First call to pool.fetch returns nothing; subsequent calls return the installed names.
    installed_names: list[str] = []
    fetch_call_count = 0

    async def fake_fetch_raw(repo_str, path):
        if "security-review" in path:
            return None
        skill_name = path.split("/")[-2]
        return f"---\nname: {skill_name}\ndescription: d\n---\nbody"

    import flow.interfaces.http.routes.skills as mod

    monkeypatch.setattr(mod, "_fetch_raw_skill", fake_fetch_raw)

    # Override pool.fetch to track installed names between calls
    async def tracking_upsert(**kwargs):
        installed_names.append(kwargs["name"])
        return uuid4()

    async def pool_fetch_side_effect(query, *args):
        nonlocal fetch_call_count
        fetch_call_count += 1
        # After the first request completes, return the installed names for deduplication
        return [{"name": n} for n in installed_names]

    repo = app.dependency_overrides[get_repo]()
    repo.upsert_agent_skill = AsyncMock(side_effect=tracking_upsert)
    repo._pool.fetch = AsyncMock(side_effect=pool_fetch_side_effect)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # First import — installs skills
        resp1 = await c.post(
            "/api/v1/skills/collections/ecc/import",
            json={"workspace_id": str(_WORKSPACE_ID)},
            headers=_auth(),
        )
        assert resp1.status_code == 201
        assert resp1.json()["installed"] >= 1

        # Second import — all non-error skills should be skipped (already installed)
        resp2 = await c.post(
            "/api/v1/skills/collections/ecc/import",
            json={"workspace_id": str(_WORKSPACE_ID)},
            headers=_auth(),
        )
    assert resp2.status_code == 201
    assert any(s["status"] == "skipped" for s in resp2.json()["steps"])


@pytest.mark.asyncio
async def test_import_unknown_collection_404(app):
    """POST /collections/does-not-exist/import should return 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/api/v1/skills/collections/does-not-exist/import",
            json={"workspace_id": str(_WORKSPACE_ID)},
            headers=_auth(),
        )
    assert resp.status_code == 404
