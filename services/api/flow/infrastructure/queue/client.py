from __future__ import annotations

from uuid import UUID

import arq
from arq import ArqRedis

from flow.config import get_settings

_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_url))
    return _pool


async def close_arq_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _trace_carrier() -> dict[str, str]:
    """Serialize the current OTel context (traceparent) for cross-process propagation."""
    try:
        from opentelemetry.propagate import inject

        carrier: dict[str, str] = {}
        inject(carrier)
        return carrier
    except Exception:
        return {}


async def enqueue_execution(
    *,
    execution_id: UUID,
    workspace_id: UUID,
    agent_id: UUID,
    user_id: UUID,
    user_message: str,
    agent_config: dict | None = None,
) -> None:
    pool = await get_arq_pool()
    await pool.enqueue_job(
        "run_deer_execution",
        str(execution_id),
        str(workspace_id),
        str(agent_id),
        str(user_id),
        user_message,
        agent_config or {},
        trace_carrier=_trace_carrier(),
    )
