"""FastAPI entry — lifespan wires DB, LangGraph checkpointer, execution stream hub."""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from flow.config import get_settings
from flow.infrastructure.observability.langsmith import configure_langsmith

configure_langsmith(get_settings())

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_fastapi_instrumentator import Instrumentator

from flow.infrastructure.db.migrate import run_migrations
from flow.infrastructure.db.pool import close_pool, create_pool
from flow.infrastructure.db.psycopg_pool import build_checkpoint_pool
from flow.infrastructure.execution_streams import ExecutionStreamHub
from flow.infrastructure.observability.logging import configure_logging, get_logger
from flow.infrastructure.observability.sentry import setup_sentry
from flow.infrastructure.observability.tracing import setup_tracing
from flow.infrastructure.queue.client import close_arq_pool, get_arq_pool
from flow.interfaces.http.routes import (
    ab_tests,
    agent_versions,
    agents,
    analytics,
    auth,
    dashboard,
    evaluations,
    executions,
    feedback,
    golden_sets,
    graph,
    health,
    kg,
    knowledge,
    logs,
    memory,
    meta,
    personas,
    preferences,
    proposals,
    schedules,
    skills,
    tools,
    trace,
    workspaces,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(
        level=settings.log_level,
        json_output=settings.log_json,
        service="flow-api",
        force_colors=settings.log_force_colors,
    )
    setup_tracing(otlp_endpoint=settings.otel_endpoint)
    setup_sentry(dsn=settings.sentry_dsn)

    run_migrations()
    pool = await create_pool(settings)
    app.state.pool = pool

    checkpoint_pool = build_checkpoint_pool(settings.database_url)
    await checkpoint_pool.open()
    checkpointer = AsyncPostgresSaver(checkpoint_pool)
    await checkpointer.setup()
    app.state.checkpoint_pool = checkpoint_pool
    app.state.checkpointer = checkpointer

    from flow.infrastructure.db.store import build_memory_store_pool, create_memory_store
    memory_store_pool = build_memory_store_pool(settings.database_url)
    await memory_store_pool.open()
    memory_store = create_memory_store(memory_store_pool)
    await memory_store.setup()
    app.state.memory_store_pool = memory_store_pool
    app.state.memory_store = memory_store

    stream_hub = ExecutionStreamHub(redis_url=settings.redis_url)
    app.state.stream_hub = stream_hub

    await get_arq_pool()

    logger.info("lifespan.started")
    try:
        yield
    finally:
        await close_arq_pool()
        await stream_hub.close()
        if hasattr(app.state, "memory_store_pool"):
            await app.state.memory_store_pool.close()
        await checkpoint_pool.close()  # type: ignore[misc]
        await close_pool(pool)
        logger.info("lifespan.stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Flow API", lifespan=lifespan)
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        t0 = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(analytics.router)
    app.include_router(dashboard.router)
    app.include_router(workspaces.router)
    app.include_router(agents.router)
    app.include_router(agent_versions.router)
    app.include_router(executions.router)
    app.include_router(feedback.router)
    app.include_router(knowledge.router)
    app.include_router(preferences.router)
    app.include_router(personas.router)
    app.include_router(proposals.router)
    app.include_router(memory.router)
    app.include_router(meta.router)
    app.include_router(schedules.router)
    app.include_router(tools.router)
    app.include_router(trace.router)
    app.include_router(logs.router)
    app.include_router(kg.router)
    app.include_router(skills.router)
    app.include_router(golden_sets.router)
    app.include_router(ab_tests.router)
    app.include_router(evaluations.router)
    app.include_router(graph.router)
    return app


app = create_app()
FastAPIInstrumentor.instrument_app(app)
AsyncPGInstrumentor().instrument()
Instrumentator().instrument(app).expose(app)
