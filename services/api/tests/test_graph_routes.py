"""Tests for /api/graph routes — workspace graph, entity subgraph, position patch."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flow.infrastructure.auth.jwt_utils import create_access_token
from flow.interfaces.http.deps import get_current_user_id, get_pool
from flow.interfaces.http.main import create_app

_SECRET = "g" * 32
_USER_ID = uuid.uuid4()
_WS_ID = uuid.uuid4()


def _auth() -> dict:
    token = create_access_token(secret=_SECRET, sub=_USER_ID)
    return {"Authorization": f"Bearer {token}"}


def _make_app(pool_mock: MagicMock):
    import os
    os.environ["FLOW_JWT_SECRET"] = _SECRET
    from flow import config as cfg
    cfg.get_settings.cache_clear()

    app = create_app()
    app.dependency_overrides[get_pool] = lambda: pool_mock
    return app


@pytest.mark.asyncio
async def test_workspace_graph_returns_nodes_and_edges():
    """GET /api/graph/workspace/{id} returns nodes and edges for the workspace."""
    node_id = uuid.uuid4()

    pool = MagicMock()
    conn = MagicMock()
    conn.fetch = AsyncMock(side_effect=[
        # first call: kg_nodes
        [{"id": node_id, "node_type": "agent", "ref_id": str(uuid.uuid4()), "ref_type": "agent",
          "label": "Bot", "metadata": {}, "pos_x": 0.0, "pos_y": 0.0}],
        # second call: kg_edges
        [],
    ])
    pool.acquire = MagicMock(return_value=conn)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)

    with patch("flow.interfaces.http.routes.graph.FlowRepository") as MockRepo:
        instance = MockRepo.return_value
        instance.list_workspaces_for_user = AsyncMock(
            return_value=[{"id": _WS_ID}]
        )
        app = _make_app(pool)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            with patch("flow.interfaces.http.routes.graph._fetch_workspace_graph") as mock_fetch:
                mock_fetch.return_value = {
                    "nodes": [{"id": str(node_id), "node_type": "agent", "label": "Bot"}],
                    "edges": [],
                }
                resp = await c.get(
                    f"/api/graph/workspace/{_WS_ID}",
                    headers=_auth(),
                )

    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data


@pytest.mark.asyncio
async def test_workspace_graph_forbidden_for_wrong_workspace():
    """Returns 403 when user has no access to the workspace."""
    pool = MagicMock()

    with patch("flow.interfaces.http.routes.graph.FlowRepository") as MockRepo:
        instance = MockRepo.return_value
        instance.list_workspaces_for_user = AsyncMock(return_value=[])  # no access
        app = _make_app(pool)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(
                f"/api/graph/workspace/{uuid.uuid4()}",
                headers=_auth(),
            )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_entity_graph_returns_one_hop():
    """GET /api/graph/entity/{type}/{ref_id} returns node + neighbours + edges."""
    node_id = uuid.uuid4()
    agent_ref_id = uuid.uuid4()
    pool = MagicMock()

    with patch("flow.interfaces.http.routes.graph.FlowRepository") as MockRepo:
        instance = MockRepo.return_value
        instance.list_workspaces_for_user = AsyncMock(
            return_value=[{"id": _WS_ID}]
        )
        app = _make_app(pool)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            with patch("flow.interfaces.http.routes.graph._fetch_entity_graph") as mock_fetch:
                mock_fetch.return_value = {
                    "node": {"id": str(node_id), "node_type": "agent"},
                    "neighbours": [],
                    "edges": [],
                }
                resp = await c.get(
                    f"/api/graph/entity/agent/{agent_ref_id}",
                    params={"workspace_id": str(_WS_ID)},
                    headers=_auth(),
                )

    assert resp.status_code == 200
    assert "node" in resp.json()


@pytest.mark.asyncio
async def test_position_patch_persists():
    """PATCH /api/graph/node/{id}/position updates x/y and returns ok."""
    node_id = uuid.uuid4()
    pool = MagicMock()

    with patch("flow.interfaces.http.routes.graph.FlowRepository") as MockRepo:
        instance = MockRepo.return_value
        instance.list_workspaces_for_user = AsyncMock(
            return_value=[{"id": _WS_ID}]
        )
        app = _make_app(pool)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            with patch("flow.interfaces.http.routes.graph._update_node_position") as mock_patch:
                mock_patch.return_value = None
                resp = await c.patch(
                    f"/api/graph/node/{node_id}/position",
                    params={"workspace_id": str(_WS_ID)},
                    json={"x": 123.4, "y": 56.7},
                    headers=_auth(),
                )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
