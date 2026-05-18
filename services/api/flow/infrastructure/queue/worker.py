# LangSmith / worker: set tracing env before any LangChain import.
from flow.config import get_settings
from flow.infrastructure.observability.langsmith import configure_langsmith

configure_langsmith(get_settings())

from uuid import UUID

import arq

from flow.application.execution_runner import run_deer_execution
from flow.application.scheduler import scheduler_tick
from flow.application.golden_evaluator import auto_eval_tick, auto_safety_eval_tick, skill_decay_tick
from flow.application.persona_freshness import persona_freshness_tick
from flow.infrastructure.db.pool import close_pool, create_pool
from flow.infrastructure.db.psycopg_pool import build_checkpoint_pool
from flow.infrastructure.execution_streams import ExecutionStreamHub
from flow.infrastructure.observability.logging import configure_logging, get_logger

logger = get_logger(__name__)


async def startup(ctx: dict) -> None:
    settings = get_settings()
    configure_logging(
        level=settings.log_level,
        json_output=settings.log_json,
        service="flow-worker",
        force_colors=settings.log_force_colors,
    )
    pool = await create_pool(settings)
    checkpoint_pool = build_checkpoint_pool(settings.database_url)
    await checkpoint_pool.open()
    from flow.infrastructure.db.store import build_memory_store_pool, create_memory_store
    memory_store_pool = build_memory_store_pool(settings.database_url)
    await memory_store_pool.open()
    memory_store = create_memory_store(memory_store_pool)
    await memory_store.setup()
    stream_hub = ExecutionStreamHub(redis_url=settings.redis_url)
    ctx["pool"] = pool
    ctx["stream_hub"] = stream_hub
    ctx["checkpoint_pool"] = checkpoint_pool
    ctx["memory_store_pool"] = memory_store_pool
    ctx["memory_store"] = memory_store
    ctx["settings"] = settings
    logger.info("worker.started", redis="configured")


async def shutdown(ctx: dict) -> None:
    if hub := ctx.get("stream_hub"):
        await hub.close()
    if msp := ctx.get("memory_store_pool"):
        await msp.close()
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
    schedule_id: str | None = None,
) -> None:
    import structlog
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    template = (
        agent_config.get("template")
        or (agent_config.get("graph") or {}).get("template", "unknown")
        or "unknown"
    )
    structlog.contextvars.bind_contextvars(
        execution_id=execution_id,
        agent_id=agent_id,
        workspace_id=workspace_id,
        template=template,
    )
    try:
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
            schedule_id=schedule_id,
            store=ctx.get("memory_store"),
        )
    finally:
        structlog.contextvars.unbind_contextvars(
            "execution_id", "agent_id", "workspace_id", "template"
        )


class WorkerSettings:
    functions = [arq.func(task_run_deer_execution, name="run_deer_execution")]
    cron_jobs = [
        arq.cron(scheduler_tick, minute=set(range(60)), run_at_startup=False),
        arq.cron(auto_eval_tick, hour=3, minute=0, run_at_startup=False),
        arq.cron(skill_decay_tick, hour=4, minute=0, run_at_startup=False),
        arq.cron(persona_freshness_tick, hour=3, minute=30, run_at_startup=False),
        arq.cron(auto_safety_eval_tick, hour=4, minute=30, run_at_startup=False),
    ]
    on_startup = startup
    on_shutdown = shutdown
    # Concrete RedisSettings required: arq passes __dict__ values to Worker and does not resolve @property.
    redis_settings = arq.connections.RedisSettings.from_dsn(get_settings().redis_url)
