"""WebSocket endpoint for real-time MetaCognition observability."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect

from flow.infrastructure.execution_streams import ExecutionStreamHub
from flow.interfaces.http.deps import get_current_user_id

router = APIRouter(prefix="/api/v1/agents/{agent_id}", tags=["observability"])
logger = logging.getLogger(__name__)


@router.websocket("/ws-observability")
async def observability_websocket(
    websocket: WebSocket,
    agent_id: UUID,
    # Note: In a real app, you'd pass a token via query params for WS auth.
    # For now, we accept the connection for local observability.
    # token: str = Query(...)
):
    """Real-time stream of agent events (MetaCog, skills, RL) for the macOS App."""
    await websocket.accept()

    # The stream hub broadcasts events to Redis channels.
    # We subscribe to the agent's channel and forward events to the WS.
    stream_hub: ExecutionStreamHub = websocket.app.state.stream_hub
    channel = f"agent_events:{agent_id}"

    pubsub = stream_hub._client.pubsub()
    await pubsub.subscribe(channel)

    try:
        # Send initial connection success
        await websocket.send_json({
            "type": "connection_established",
            "agent_id": str(agent_id),
            "status": "listening"
        })

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json(data)
                except Exception:
                    pass
            await asyncio.sleep(0.01)  # Yield loop

    except WebSocketDisconnect:
        logger.info(f"Observability WS disconnected for agent {agent_id}")
    except Exception as e:
        logger.error(f"Observability WS error: {e}")
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
