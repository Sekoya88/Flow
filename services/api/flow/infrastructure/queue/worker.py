# LangSmith / worker: set tracing env before any LangChain import.
from flow.config import get_settings
from flow.infrastructure.observability.langsmith import configure_langsmith

configure_langsmith(get_settings())

from uuid import UUID

import arq

from flow.application.execution_runner import run_deer_execution
from flow.application.golden_evaluator import auto_eval_tick, auto_safety_eval_tick, skill_decay_tick
from flow.application.persona_freshness import persona_freshness_tick
from flow.application.scheduler import scheduler_tick
from flow.infrastructure.db.pool import close_pool, create_pool
from flow.infrastructure.db.psycopg_pool import build_checkpoint_pool
from flow.infrastructure.execution_streams import ExecutionStreamHub
from flow.infrastructure.graph.research_digest_graph import run_research_digest as _run_digest
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

    template = agent_config.get("template") or (agent_config.get("graph") or {}).get("template", "unknown") or "unknown"
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
        structlog.contextvars.unbind_contextvars("execution_id", "agent_id", "workspace_id", "template")


async def task_run_research_digest(ctx: dict, workspace_id: str, config: dict) -> dict:
    return await _run_digest(workspace_id, config, stream_hub=ctx.get("stream_hub"))


async def research_digest_tick(ctx: dict) -> None:
    """Fan out a digest run to every workspace with digest enabled."""
    pool = ctx.get("pool")
    if pool is None:
        return
    rows = await pool.fetch("SELECT workspace_id, row_to_json(wdc)::text AS cfg FROM workspace_digest_config wdc WHERE enabled = true")
    arq_pool = ctx.get("arq_pool")
    if arq_pool is None:
        from flow.infrastructure.queue.client import get_arq_pool

        arq_pool = await get_arq_pool()

    for row in rows:
        import json as _json

        config = _json.loads(row["cfg"]) if isinstance(row["cfg"], str) else dict(row)
        await arq_pool.enqueue_job("run_research_digest", str(row["workspace_id"]), config)


async def task_run_skill_training(
    ctx: dict,
    run_id: str,
    skill_id: str,
    agent_id: str,
    workspace_id: str,
    config_dict: dict,
) -> dict:
    """Run a ReflACT training epoch for a skill.

    All ID args are str (ARQ serializes UUIDs as strings).
    Runs all epochs in config_dict['max_epochs'], stops early if accepted=True.
    Updates skill_training_runs status throughout.
    """
    from uuid import UUID as _UUID

    from flow.application.skill_trainer import SkillTrainer, TrainingConfig
    from flow.infrastructure.persistence.repo import FlowRepository

    pool = ctx["pool"]
    stream_hub = ctx.get("stream_hub")
    repo = FlowRepository(pool)
    trainer = SkillTrainer(pool)
    config = TrainingConfig(**config_dict)

    _run_id = _UUID(run_id)
    _skill_id = _UUID(skill_id)
    _agent_id = _UUID(agent_id)
    _workspace_id = _UUID(workspace_id)

    await repo.update_training_run(_run_id, status="running", started_at=True)
    if stream_hub:
        await stream_hub.publish_global(workspace_id, kind="skill.training.started", payload={
            "run_id": run_id, "skill_id": skill_id,
        })

    best_score = None
    final_accepted = False

    try:
        for epoch in range(config.max_epochs):
            await repo.update_training_run(_run_id, epoch=epoch)

            result = await trainer.run_training_epoch(
                run_id=_run_id,
                skill_id=_skill_id,
                agent_id=_agent_id,
                workspace_id=_workspace_id,
                config=config,
                pool=pool,
            )

            await repo.insert_training_epoch(
                run_id=_run_id,
                epoch=epoch,
                candidate_skill_id=result.get("candidate_skill_id"),
                eval_score=result.get("eval_score", 0.0),
                baseline_score=result.get("baseline_score", 0.0),
                accepted=result.get("accepted", False),
                patch_count=result.get("patches_applied", 0),
            )

            eval_score = result.get("eval_score", 0.0)
            if best_score is None or eval_score > best_score:
                best_score = eval_score

            await repo.update_training_run(
                _run_id,
                edits_used=result.get("patches_applied", 0),
                best_score=best_score,
                accepted=result.get("accepted", False),
            )

            if stream_hub:
                await stream_hub.publish_global(workspace_id, kind="skill.training.epoch", payload={
                    "run_id": run_id, "skill_id": skill_id, "epoch": epoch,
                    "eval_score": eval_score, "accepted": result.get("accepted", False),
                })

            if result.get("accepted"):
                final_accepted = True
                # Activate the candidate skill
                candidate_id = result.get("candidate_skill_id")
                if candidate_id:
                    await pool.execute(
                        "UPDATE agent_skills SET active = true WHERE id = $1",
                        candidate_id,
                    )
                    await pool.execute(
                        "UPDATE agent_skills SET last_training_run_id = $1 WHERE id = $2",
                        _run_id, _skill_id,
                    )
                    # KG tracking: upsert node for improved skill, edge from original
                    try:
                        eval_score = result.get("eval_score", 0.0)
                        baseline_score = result.get("baseline_score", 0.0)
                        delta = eval_score - baseline_score
                        new_node_id = await repo.upsert_kg_node(
                            workspace_id=_workspace_id,
                            label=f"skill:{candidate_id}",
                            node_type="skill",
                            summary=f"ReflACT epoch {epoch}, Δ+{delta:.3f} → {eval_score:.3f}",
                            metadata={
                                "run_id": str(_run_id),
                                "epoch": epoch,
                                "eval_score": eval_score,
                                "baseline_score": baseline_score,
                                "patches_applied": result.get("patches_applied", 0),
                            },
                        )
                        old_node = await repo.get_kg_node_by_label(
                            _workspace_id, f"skill:{_skill_id}", "skill"
                        )
                        if old_node:
                            await repo.upsert_kg_edge(
                                workspace_id=_workspace_id,
                                source_id=old_node["id"],
                                target_id=new_node_id,
                                edge_type="improved_by",
                                metadata={"trigger": "reflact", "epoch": epoch},
                            )
                    except Exception as _kg_exc:
                        logger.warning("skill training KG update failed: %s", _kg_exc)
                    # Genome snapshot
                    try:
                        from flow.application.genome_service import snapshot_genome
                        from flow.domain.genome import VersionTrigger
                        await snapshot_genome(
                            pool=pool,
                            agent_id=_agent_id,
                            workspace_id=_workspace_id,
                            trigger=VersionTrigger.SKILL_TRAIN,
                            version_label=f"reflact-{run_id[:8]}",
                        )
                    except Exception as _snap_exc:
                        logger.warning("skill training genome snapshot failed: %s", _snap_exc)
                break  # early stop after acceptance

        await repo.update_training_run(
            _run_id,
            status="done",
            accepted=final_accepted,
            completed_at=True,
        )
        if stream_hub:
            await stream_hub.publish_global(workspace_id, kind="skill.training.done", payload={
                "run_id": run_id, "skill_id": skill_id,
                "accepted": final_accepted, "best_score": best_score,
            })

    except Exception as exc:
        logger.error("task_run_skill_training failed: run_id=%s err=%s", run_id, exc)
        await repo.update_training_run(_run_id, status="failed", error_message=str(exc), completed_at=True)
        if stream_hub:
            await stream_hub.publish_global(workspace_id, kind="skill.training.failed", payload={
                "run_id": run_id, "skill_id": skill_id, "error": str(exc),
            })
        raise

    return {"run_id": run_id, "accepted": final_accepted, "best_score": best_score}


async def skill_training_tick(ctx: dict) -> None:
    """Daily cron (05:00 UTC): enqueue training for skills with training_mode='react'.

    Only enqueues skills not trained in the last 24 hours.
    """
    pool = ctx.get("pool")
    if pool is None:
        return

    rows = await pool.fetch(
        """
        SELECT s.id AS skill_id, s.agent_id, s.workspace_id
        FROM agent_skills s
        WHERE s.training_mode = 'react'
          AND s.active = true
          AND (
              s.last_training_run_id IS NULL
              OR (
                  SELECT completed_at FROM skill_training_runs
                  WHERE id = s.last_training_run_id
              ) < now() - interval '24 hours'
          )
        """
    )

    if not rows:
        return

    from flow.infrastructure.queue.client import get_arq_pool

    arq_pool = await get_arq_pool()
    default_config = {"edit_budget": 5, "max_epochs": 3}

    for row in rows:
        from flow.infrastructure.persistence.repo import FlowRepository

        repo = FlowRepository(pool)
        created_run_id = await repo.create_training_run(
            skill_id=row["skill_id"],
            agent_id=row["agent_id"],
            workspace_id=row["workspace_id"],
            edit_budget=default_config["edit_budget"],
        )
        await arq_pool.enqueue_job(
            "run_skill_training",
            str(created_run_id),
            str(row["skill_id"]),
            str(row["agent_id"]),
            str(row["workspace_id"]),
            default_config,
        )


class WorkerSettings:
    functions = [
        arq.func(task_run_deer_execution, name="run_deer_execution"),
        arq.func(task_run_research_digest, name="run_research_digest"),
        arq.func(task_run_skill_training, name="run_skill_training"),
    ]
    cron_jobs = [
        arq.cron(scheduler_tick, minute=set(range(60)), run_at_startup=False),
        arq.cron(auto_eval_tick, hour=3, minute=0, run_at_startup=False),
        arq.cron(skill_decay_tick, hour=4, minute=0, run_at_startup=False),
        arq.cron(persona_freshness_tick, hour=3, minute=30, run_at_startup=False),
        arq.cron(auto_safety_eval_tick, hour=4, minute=30, run_at_startup=False),
        arq.cron(research_digest_tick, hour=8, minute=0, run_at_startup=False),
        arq.cron(skill_training_tick, hour=5, minute=0, run_at_startup=False),
    ]
    on_startup = startup
    on_shutdown = shutdown
    # Concrete RedisSettings required: arq passes __dict__ values to Worker and does not resolve @property.
    redis_settings = arq.connections.RedisSettings.from_dsn(get_settings().redis_url)
