"""Integration tests for /api/v1/agents/{id}/ws-observability WebSocket endpoint."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import FastAPI
from starlette.testclient import TestClient

from flow.interfaces.http.routes import observability_ws


def _make_pubsub_mock(messages: list[dict]):
    """Fake pubsub that yields messages then blocks."""

    async def _listen():
        for msg in messages:
            yield {"type": "message", "data": json.dumps(msg)}
        await asyncio.sleep(60)  # keep WS alive while client reads

    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    pubsub.close = AsyncMock()
    pubsub.listen = _listen
    return pubsub


def _make_stream_hub(pubsub):
    hub = MagicMock()
    hub._client.pubsub.return_value = pubsub
    return hub


def _make_app(pubsub) -> FastAPI:
    """Minimal app with only the observability router and mocked state."""
    app = FastAPI()
    app.include_router(observability_ws.router)
    app.state.stream_hub = _make_stream_hub(pubsub)
    return app


def test_ws_receives_published_event():
    """Should forward a Redis pub/sub message to the WebSocket client."""
    agent_id = uuid4()
    event = {"type": "skills_matched", "skills": [{"name": "search", "version": "1"}]}

    app = _make_app(_make_pubsub_mock([event]))

    with TestClient(app) as client:
        with client.websocket_connect(f"/api/v1/agents/{agent_id}/ws-observability") as ws:
            handshake = ws.receive_json()
            assert handshake["type"] == "connection_established"
            assert handshake["agent_id"] == str(agent_id)

            received = ws.receive_json()
            assert received["type"] == "skills_matched"
            assert received["skills"][0]["name"] == "search"


def test_ws_handshake_contains_agent_id():
    """Should include agent_id and status in connection_established."""
    agent_id = uuid4()
    app = _make_app(_make_pubsub_mock([]))

    with TestClient(app) as client:
        with client.websocket_connect(f"/api/v1/agents/{agent_id}/ws-observability") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "connection_established"
            assert msg["status"] == "listening"
            assert msg["agent_id"] == str(agent_id)


def test_ws_subscribes_to_correct_channel():
    """Should subscribe to agent_events:{agent_id} and unsubscribe on close."""
    agent_id = uuid4()
    pubsub = _make_pubsub_mock([])
    app = _make_app(pubsub)

    with TestClient(app) as client:
        with client.websocket_connect(f"/api/v1/agents/{agent_id}/ws-observability") as ws:
            ws.receive_json()  # consume handshake

    pubsub.subscribe.assert_called_once_with(f"agent_events:{agent_id}")
    pubsub.unsubscribe.assert_called_once_with(f"agent_events:{agent_id}")
