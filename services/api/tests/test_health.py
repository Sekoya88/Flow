from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from flow.interfaces.http.main import create_app


@pytest.mark.asyncio
async def test_health_no_db_degraded(monkeypatch):
    app = create_app()

    app.state.pool = None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["db"] is False


def test_health_with_db(database_url: str, monkeypatch):
    monkeypatch.setenv("FLOW_DATABASE_URL", database_url)
    monkeypatch.setenv("FLOW_JWT_SECRET", "0123456789abcdef0123456789abcdef")
    from flow import config as cfg

    cfg.get_settings.cache_clear()

    from flow.interfaces.http.main import create_app

    app = create_app()
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["db"] is True
