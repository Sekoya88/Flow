"""Tests for /api/v1/integrations/telegram routes."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from flow.infrastructure.auth.jwt_utils import create_access_token
from flow.interfaces.http.deps import get_pool
from flow.interfaces.http.main import create_app

_SECRET = "a" * 32
_USER_ID = uuid4()
_WS_ID = uuid4()
_AGENT_ID = uuid4()
_BOT_ID = uuid4()
_WEBHOOK_SECRET = "s3cr3t"
_BOT_TOKEN = "123456:ABCDef"
_BOT_USERNAME = "myflowbot"


def _auth() -> dict:
    return {"Authorization": f"Bearer {create_access_token(secret=_SECRET, sub=_USER_ID)}"}


def _make_bot_row(**overrides) -> dict:
    base = {
        "id": _BOT_ID,
        "workspace_id": _WS_ID,
        "agent_id": _AGENT_ID,
        "user_id": _USER_ID,
        "bot_token": _BOT_TOKEN,
        "bot_username": _BOT_USERNAME,
        "webhook_secret": _WEBHOOK_SECRET,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    return {**base, **overrides}


def _make_pool(
    *,
    member=True,
    agent=True,
    bot_row=None,
    bot_list=None,
    new_bot_id=None,
) -> MagicMock:
    pool = MagicMock()

    async def fetchrow_side_effect(query, *args):
        q = query.strip().upper()
        if "WORKSPACE_MEMBERS" in q:
            return {"1": 1} if member else None
        if "AGENTS" in q and "WORKSPACE_ID" in q:
            return {"id": _AGENT_ID} if agent else None
        if "TELEGRAM_BOTS" in q:
            return _make_bot_row() if bot_row is None else bot_row
        return None

    pool.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    pool.fetch = AsyncMock(
        return_value=bot_list
        if bot_list is not None
        else [
            {
                "id": _BOT_ID,
                "agent_id": _AGENT_ID,
                "bot_username": _BOT_USERNAME,
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "agent_name": "Test Agent",
            }
        ]
    )
    pool.fetchval = AsyncMock(return_value=new_bot_id or _BOT_ID)
    pool.execute = AsyncMock()
    return pool


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLOW_JWT_SECRET", _SECRET)
    from flow import config as cfg

    cfg.get_settings.cache_clear()
    _app = create_app()
    pool = _make_pool()
    _app.dependency_overrides[get_pool] = lambda: pool
    return _app


# ── Register bot ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_bot_success(app):
    pool = _make_pool()
    app.dependency_overrides[get_pool] = lambda: pool

    with (
        patch("flow.interfaces.http.routes.integrations.get_me", new_callable=AsyncMock)
        as mock_get_me,
        patch(
            "flow.interfaces.http.routes.integrations.register_webhook",
            new_callable=AsyncMock,
        ),
    ):
        mock_get_me.return_value = {"result": {"username": _BOT_USERNAME}}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/api/v1/integrations/telegram",
                json={
                    "workspace_id": str(_WS_ID),
                    "agent_id": str(_AGENT_ID),
                    "bot_token": _BOT_TOKEN,
                },
                headers=_auth(),
            )

    assert r.status_code == 201
    data = r.json()
    assert data["bot_username"] == _BOT_USERNAME
    assert "webhook_url" in data
    assert str(_BOT_ID) in data["webhook_url"]


@pytest.mark.asyncio
async def test_register_bot_invalid_token(app):
    pool = _make_pool()
    app.dependency_overrides[get_pool] = lambda: pool

    with patch(
        "flow.interfaces.http.routes.integrations.get_me",
        new_callable=AsyncMock,
        side_effect=Exception("Unauthorized"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/api/v1/integrations/telegram",
                json={
                    "workspace_id": str(_WS_ID),
                    "agent_id": str(_AGENT_ID),
                    "bot_token": "bad-token",
                },
                headers=_auth(),
            )

    assert r.status_code == 400
    assert "invalid bot token" in r.json()["detail"]


@pytest.mark.asyncio
async def test_register_bot_non_member(app):
    pool = _make_pool(member=False)
    app.dependency_overrides[get_pool] = lambda: pool

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/integrations/telegram",
            json={
                "workspace_id": str(_WS_ID),
                "agent_id": str(_AGENT_ID),
                "bot_token": _BOT_TOKEN,
            },
            headers=_auth(),
        )

    assert r.status_code == 403


# ── List bots ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_bots(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            f"/api/v1/integrations/telegram?workspace_id={_WS_ID}", headers=_auth()
        )

    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["bot_username"] == _BOT_USERNAME
    assert data[0]["agent_name"] == "Test Agent"


@pytest.mark.asyncio
async def test_list_bots_empty(app):
    pool = _make_pool(bot_list=[])
    app.dependency_overrides[get_pool] = lambda: pool

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            f"/api/v1/integrations/telegram?workspace_id={_WS_ID}", headers=_auth()
        )

    assert r.status_code == 200
    assert r.json() == []


# ── Delete bot ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_bot(app):
    with patch(
        "flow.interfaces.http.routes.integrations.delete_webhook",
        new_callable=AsyncMock,
    ) as mock_del:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.delete(
                f"/api/v1/integrations/telegram/{_BOT_ID}?workspace_id={_WS_ID}",
                headers=_auth(),
            )

    assert r.status_code == 204
    mock_del.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_bot_not_found(app):
    pool = _make_pool()

    async def fetchrow_not_found(query, *args):
        q = query.strip().upper()
        if "WORKSPACE_MEMBERS" in q:
            return {"1": 1}
        return None

    pool.fetchrow = AsyncMock(side_effect=fetchrow_not_found)
    app.dependency_overrides[get_pool] = lambda: pool

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.delete(
            f"/api/v1/integrations/telegram/{uuid4()}?workspace_id={_WS_ID}",
            headers=_auth(),
        )

    assert r.status_code == 404


# ── Webhook receiver ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_webhook_valid_secret_returns_ok(app):
    update = {
        "update_id": 1,
        "message": {
            "message_id": 42,
            "chat": {"id": 99, "type": "private"},
            "text": "hello agent",
            "from": {"id": 999},
        },
    }

    with patch(
        "flow.interfaces.http.routes.integrations._handle_message",
        new_callable=AsyncMock,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                f"/api/v1/integrations/telegram/{_BOT_ID}/webhook",
                json=update,
                headers={"x-telegram-bot-api-secret-token": _WEBHOOK_SECRET},
            )

    assert r.status_code == 200
    assert r.json() == {"ok": True}


@pytest.mark.asyncio
async def test_webhook_bad_secret_returns_403(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            f"/api/v1/integrations/telegram/{_BOT_ID}/webhook",
            json={"update_id": 1, "message": {"chat": {"id": 1}, "text": "x"}},
            headers={"x-telegram-bot-api-secret-token": "wrong"},
        )

    assert r.status_code == 403


@pytest.mark.asyncio
async def test_webhook_no_text_returns_ok(app):
    """Non-text messages (stickers, photos) should return 200 without doing anything."""
    update = {
        "update_id": 2,
        "message": {
            "chat": {"id": 99, "type": "private"},
            "sticker": {"file_id": "abc"},
        },
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            f"/api/v1/integrations/telegram/{_BOT_ID}/webhook",
            json=update,
            headers={"x-telegram-bot-api-secret-token": _WEBHOOK_SECRET},
        )

    assert r.status_code == 200
    assert r.json() == {"ok": True}


@pytest.mark.asyncio
async def test_webhook_unknown_bot_returns_ok(app):
    """Unknown bot_id must not raise — Telegram retries aggressively."""
    pool = _make_pool()

    async def fetchrow_no_bot(query, *args):
        return None

    pool.fetchrow = AsyncMock(side_effect=fetchrow_no_bot)
    app.dependency_overrides[get_pool] = lambda: pool

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            f"/api/v1/integrations/telegram/{uuid4()}/webhook",
            json={"update_id": 3, "message": {"chat": {"id": 1}, "text": "x"}},
            headers={"x-telegram-bot-api-secret-token": "any"},
        )

    assert r.status_code == 200
    assert r.json() == {"ok": True}
