from __future__ import annotations

import asyncio
import json
from uuid import UUID

import redis.asyncio as aioredis


class ExecutionStreamHub:
    def __init__(self, redis_url: str) -> None:
        self._client = aioredis.from_url(redis_url, decode_responses=True)

    def publish(self, execution_id: UUID, event: dict) -> None:
        asyncio.create_task(self._publish(execution_id, event))

    async def _publish(self, execution_id: UUID, event: dict) -> None:
        await self._client.publish(f"flow:exec:{execution_id}", json.dumps(event))

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

    async def close(self) -> None:
        await self._client.aclose()
