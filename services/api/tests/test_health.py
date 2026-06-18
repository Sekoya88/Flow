from __future__ import annotations

import time

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
        # The DB pool initialises in a background task — lifespan yields immediately
        # so the platform healthcheck passes — so db readiness is eventually
        # consistent. Poll until the pool connects (or time out).
        deadline = time.monotonic() + 15
        body: dict = {}
        while time.monotonic() < deadline:
            r = client.get("/health")
            assert r.status_code == 200
            body = r.json()
            if body.get("db") is True:
                break
            time.sleep(0.25)
    assert body.get("db") is True
