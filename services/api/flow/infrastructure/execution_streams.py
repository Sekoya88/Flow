from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis

from flow.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class ExecutionStreamHub:
    def __init__(self, redis_url: str) -> None:
        self._client = aioredis.from_url(redis_url, decode_responses=True)

    def publish(self, execution_id: UUID, event: dict) -> None:
        asyncio.create_task(self._publish(execution_id, event))

    async def _publish(self, execution_id: UUID, event: dict) -> None:
        await self._client.publish(f"flow:exec:{execution_id}", json.dumps(event))

    def publish_agent_event(self, agent_id: UUID, event: dict) -> None:
        """Broadcast an event (metacog, skill matching) to the agent's observability channel."""
        asyncio.create_task(self._publish_agent_event(agent_id, event))

    async def _publish_agent_event(self, agent_id: UUID, event: dict) -> None:
        await self._client.publish(f"agent_events:{agent_id}", json.dumps(event))
        # Track this agent as recently active (TTL 2h) for local discovery
        await self._client.setex(f"active_agent:{agent_id}", 7200, "1")

    async def get_active_agent_ids(self) -> list[str]:
        """Return agent IDs that have had events in the last 2 hours."""
        keys = await self._client.keys("active_agent:*")
        return [k.replace("active_agent:", "") for k in keys]

    async def publish_global(self, workspace_id: str, kind: str, payload: dict) -> None:
        """Broadcast a workspace-scoped event to the global stream channel."""
        event = {"kind": kind, **payload}
        await self._client.publish(f"flow:global:{workspace_id}", json.dumps(event))

    async def subscribe(self, execution_id: UUID):
        pubsub = self._client.pubsub()
        await pubsub.subscribe(f"flow:exec:{execution_id}")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(f"flow:exec:{execution_id}")
            await pubsub.aclose()

    async def subscribe_global(self, workspace_id: str):
        pubsub = self._client.pubsub()
        await pubsub.subscribe(f"flow:global:{workspace_id}")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(f"flow:global:{workspace_id}")
            await pubsub.aclose()

    async def close(self) -> None:
        await self._client.aclose()


class ExecutionEventEmitter:
    """Single emission path for execution events: DB persist + Redis publish + structured log.

    Persisted events carry their `execution_events.id` so the SSE layer can send
    `id:` on live frames too, making `Last-Event-ID` resume reliable mid-stream.
    High-frequency deltas (tokens, tool output chunks) can opt out of persistence
    with `persist=False` — they remain live-only on Redis.
    """

    def __init__(self, hub: ExecutionStreamHub, pool: Any) -> None:
        self._hub = hub
        self._pool = pool

    async def emit(
        self,
        execution_id: UUID,
        kind: str,
        payload: dict[str, Any],
        *,
        persist: bool = True,
    ) -> int | None:
        event_id: int | None = None
        if persist and self._pool is not None:
            try:
                event_id = await self._pool.fetchval(
                    """
                    INSERT INTO execution_events (execution_id, kind, payload)
                    VALUES ($1, $2, $3::jsonb)
                    RETURNING id
                    """,
                    execution_id,
                    kind,
                    json.dumps(payload),
                )
            except Exception as exc:
                logger.warning("event.persist_failed", kind=kind, error=str(exc))
        event: dict[str, Any] = {"kind": kind, **payload}
        if event_id is not None:
            event["id"] = event_id
        self._hub.publish(execution_id, event)
        try:
            from flow.infrastructure.observability.metrics import record_event

            record_event(execution_id, kind, payload)
        except Exception:
            pass
        return event_id

    def emit_nowait(
        self,
        execution_id: UUID,
        kind: str,
        payload: dict[str, Any],
        *,
        persist: bool = True,
    ) -> None:
        """Fire-and-forget variant for sync call sites (tool wrappers, callbacks)."""
        asyncio.ensure_future(self.emit(execution_id, kind, payload, persist=persist))
