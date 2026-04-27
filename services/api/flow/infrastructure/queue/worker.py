from __future__ import annotations

from uuid import UUID

import arq

from flow.application.execution_runner import run_deer_execution
from flow.config import get_settings
from flow.infrastructure.db.pool import close_pool, create_pool
from flow.infrastructure.db.psycopg_pool import build_checkpoint_pool
from flow.infrastructure.execution_streams import ExecutionStreamHub


async def startup(ctx: dict) -> None:
    settings = get_settings()
    pool = await create_pool(settings)
    checkpoint_pool = build_checkpoint_pool(settings.database_url)
    await checkpoint_pool.open()
    stream_hub = ExecutionStreamHub(redis_url=settings.redis_url)
    ctx["pool"] = pool
    ctx["stream_hub"] = stream_hub
    ctx["checkpoint_pool"] = checkpoint_pool
    ctx["settings"] = settings


async def shutdown(ctx: dict) -> None:
    if hub := ctx.get("stream_hub"):
        await hub.close()
    if cp := ctx.get("checkpoint_pool"):
        await cp.close()
    if pool := ctx.get("pool"):
        await close_pool(pool)


async def task_run_deer_execution(
    ctx: dict,
    execution_id: str,
    workspace_id: str,
    agent_id: str,
    user_id: str,
    user_message: str,
    agent_config: dict,
) -> None:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    checkpointer = AsyncPostgresSaver(ctx["checkpoint_pool"])
    await run_deer_execution(
        pool=ctx["pool"],
        settings=ctx["settings"],
        stream_hub=ctx["stream_hub"],
        checkpointer=checkpointer,
        execution_id=UUID(execution_id),
        workspace_id=UUID(workspace_id),
        agent_id=UUID(agent_id),
        user_id=UUID(user_id),
        user_message=user_message,
        agent_config=agent_config,
    )


class WorkerSettings:
    functions = [arq.func(task_run_deer_execution, name="run_deer_execution")]
    on_startup = startup
    on_shutdown = shutdown
    # Concrete RedisSettings required: arq passes __dict__ values to Worker and does not resolve @property.
    redis_settings = arq.connections.RedisSettings.from_dsn(get_settings().redis_url)
