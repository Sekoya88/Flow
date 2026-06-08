"""Tests: execute_agent injects _jwt_token + use_mcp when workspace has active MCP servers."""

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
_AGENT_ID = uuid4()
_EXEC_ID = uuid4()
_THREAD_ID = uuid4()


def _auth() -> dict:
    return {"Authorization": f"Bearer {create_access_token(secret=_SECRET, sub=_USER_ID)}"}


def _make_agent_row(config: dict | None = None) -> dict:
    return {
        "id": _AGENT_ID,
        "workspace_id": _WS_ID,
        "name": "Test Agent",
        "template": "linear-3",
        "config": config or {"graph": {"template": "linear-3"}},
    }


def _make_repo(active_mcp_count: int = 0, agent_config: dict | None = None) -> FlowRepository:
    repo = MagicMock(spec=FlowRepository)
    repo.list_workspaces_for_user = AsyncMock(return_value=[{"id": _WS_ID}])
    repo.get_agent = AsyncMock(return_value=_make_agent_row(agent_config))
    repo.get_execution_for_user = AsyncMock(return_value=None)
    repo.create_execution = AsyncMock(return_value=(_EXEC_ID, _THREAD_ID))

    pool = MagicMock()
    pool.fetchval = AsyncMock(return_value=active_mcp_count)
    repo._pool = pool
    return repo


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLOW_JWT_SECRET", _SECRET)
    from flow import config as cfg

    cfg.get_settings.cache_clear()
    return create_app()


@pytest.mark.asyncio
async def test_execute_injects_mcp_token_when_active_servers(app):
    """When workspace has active MCP servers, _jwt_token and use_mcp=True injected."""
    repo = _make_repo(active_mcp_count=2)
    app.dependency_overrides[get_repo] = lambda: repo
    captured: dict = {}

    async def fake_enqueue(**kwargs):
        captured.update(kwargs)

    with patch("flow.infrastructure.queue.client.enqueue_execution", side_effect=fake_enqueue):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/agents/{_AGENT_ID}/execute",
                json={"message": "hello"},
                headers=_auth(),
            )

    assert resp.status_code == 200
    cfg = captured.get("agent_config", {})
    assert cfg.get("_jwt_token"), "_jwt_token should be injected"
    assert cfg.get("tools", {}).get("use_mcp") is True, "use_mcp should be True"


@pytest.mark.asyncio
async def test_execute_no_mcp_when_no_active_servers(app):
    """When workspace has no active MCP servers, _jwt_token not injected."""
    repo = _make_repo(active_mcp_count=0)
    app.dependency_overrides[get_repo] = lambda: repo
    captured: dict = {}

    async def fake_enqueue(**kwargs):
        captured.update(kwargs)

    with patch("flow.infrastructure.queue.client.enqueue_execution", side_effect=fake_enqueue):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/agents/{_AGENT_ID}/execute",
                json={"message": "hello"},
                headers=_auth(),
            )

    assert resp.status_code == 200
    cfg = captured.get("agent_config", {})
    assert "_jwt_token" not in cfg, "_jwt_token should NOT be injected"
    assert not cfg.get("tools", {}).get("use_mcp"), "use_mcp should not be set"


@pytest.mark.asyncio
async def test_execute_preserves_existing_tools_config(app):
    """Existing tools config (e.g. tavily_search=True) preserved when MCP injected."""
    existing_cfg = {"graph": {"template": "tool-agent"}, "tools": {"tavily_search": True}}
    repo = _make_repo(active_mcp_count=1, agent_config=existing_cfg)
    app.dependency_overrides[get_repo] = lambda: repo
    captured: dict = {}

    async def fake_enqueue(**kwargs):
        captured.update(kwargs)

    with patch("flow.infrastructure.queue.client.enqueue_execution", side_effect=fake_enqueue):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/agents/{_AGENT_ID}/execute",
                json={"message": "hello"},
                headers=_auth(),
            )

    assert resp.status_code == 200
    tools = captured.get("agent_config", {}).get("tools", {})
    assert tools.get("tavily_search") is True, "existing tools config preserved"
    assert tools.get("use_mcp") is True, "use_mcp added alongside existing tools"
