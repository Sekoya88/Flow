"""Integration test for POST /api/v1/knowledge/chunks/{chunk_id}/promote."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from flow.infrastructure.auth.jwt_utils import create_access_token
from flow.interfaces.http.deps import get_repo
from flow.interfaces.http.main import create_app

_SECRET = "k" * 32
_USER_ID = uuid.uuid4()
_WS_ID = uuid.uuid4()
_AGENT_ID = uuid.uuid4()


def _auth() -> dict:
    token = create_access_token(secret=_SECRET, sub=_USER_ID)
    return {"Authorization": f"Bearer {token}"}


def _make_app(fake_repo: MagicMock):
    import os

    os.environ["FLOW_JWT_SECRET"] = _SECRET
    from flow import config as cfg

    cfg.get_settings.cache_clear()

    app = create_app()
    app.dependency_overrides[get_repo] = lambda: fake_repo
    return app


@pytest.mark.asyncio
async def test_promote_chunk_returns_memory_id():
    memory_id = uuid.uuid4()
    fake_repo = MagicMock()
    fake_repo.list_workspaces_for_user = AsyncMock(return_value=[{"id": _WS_ID}])
    fake_repo.promote_chunk_to_memory = AsyncMock(return_value=memory_id)

    app = _make_app(fake_repo)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/api/v1/knowledge/chunks/42/promote",
            json={"workspace_id": str(_WS_ID), "agent_id": str(_AGENT_ID)},
            headers=_auth(),
        )

    assert resp.status_code == 201
    assert resp.json() == {"memory_id": str(memory_id)}
    fake_repo.promote_chunk_to_memory.assert_awaited_once_with(_WS_ID, _AGENT_ID, _USER_ID, 42)


@pytest.mark.asyncio
async def test_promote_chunk_404_when_chunk_not_found():
    fake_repo = MagicMock()
    fake_repo.list_workspaces_for_user = AsyncMock(return_value=[{"id": _WS_ID}])
    fake_repo.promote_chunk_to_memory = AsyncMock(return_value=None)

    app = _make_app(fake_repo)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/api/v1/knowledge/chunks/999/promote",
            json={"workspace_id": str(_WS_ID), "agent_id": str(_AGENT_ID)},
            headers=_auth(),
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_promote_chunk_forbidden_for_wrong_workspace():
    fake_repo = MagicMock()
    fake_repo.list_workspaces_for_user = AsyncMock(return_value=[])  # no access
    fake_repo.promote_chunk_to_memory = AsyncMock()

    app = _make_app(fake_repo)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/api/v1/knowledge/chunks/42/promote",
            json={"workspace_id": str(_WS_ID), "agent_id": str(_AGENT_ID)},
            headers=_auth(),
        )

    assert resp.status_code == 403
    fake_repo.promote_chunk_to_memory.assert_not_awaited()
