from __future__ import annotations

import json
import time as _time
from typing import Any
from uuid import UUID

import asyncpg
from langchain_core.messages import HumanMessage

from flow.config import Settings
from flow.infrastructure.execution_streams import ExecutionStreamHub
from flow.infrastructure.graph.deer_graph import GraphContext
from flow.infrastructure.graph.entity_indexer import index_execution as _index_execution
from flow.infrastructure.llm.agent_factory import build_agent_from_ctx
from flow.infrastructure.observability.logging import get_logger
from flow.infrastructure.persistence.repo import FlowRepository

logger = get_logger(__name__)


def _log_banner(log, event: str, **kw) -> None:
    """Emit a structured log entry used as a visual execution delimiter in Docker logs."""
    log.info(event, **kw)


async def _get_schedule_delivery(pool, schedule_id: str) -> dict | None:
    """Fetch delivery config for a schedule. Returns None on any failure."""
    try:
        from uuid import UUID as _UUID
        row = await pool.fetchrow(
            "SELECT delivery_type, delivery_target FROM agent_schedules WHERE id = $1",
            _UUID(schedule_id),
        )
        if row:
            return {"type": row["delivery_type"], "target": row["delivery_target"]}
    except Exception:
        pass
    return None


async def _fire_webhook(url: str, execution_id: str, agent_id: str, answer: str) -> None:
    """POST execution result to webhook URL. Best-effort."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={
                "execution_id": execution_id,
                "agent_id": agent_id,
                "answer": answer,
            })
    except Exception as exc:
        logger.warning("webhook delivery failed: %s", exc)


def _json_safe(obj: Any) -> Any:
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        if isinstance(obj, dict):
            return {k: _json_safe(v) for k, v in obj.items()}
        return str(obj)


def _summarize_node_partial(node_name: str, partial: Any) -> str:
    """Short line for SSE / concise UI. Full graph state remains in stored payload."""
    if partial is None:
        return f"{node_name} · —"
    if not isinstance(partial, dict):
        return f"{node_name} · update"
    tags: list[str] = []
    if isinstance(partial.get("plan"), str) and partial["plan"].strip():
        tags.append("plan")
    if partial.get("worker_output") is not None:
        tags.append("worker output")
    if partial.get("answer") is not None:
        tags.append("answer")
    msgs = partial.get("messages")
    n_msg = len(msgs) if isinstance(msgs, list) else 0
    if n_msg:
        tags.append(f"+{n_msg} msg")
        last = msgs[-1]
        blob = getattr(last, "content", None)
        if blob is None and isinstance(last, dict):
            blob = last.get("content")
        if isinstance(blob, str) and "```python" in blob:
            tags.append("sandbox")
    return f"{node_name} · " + (" · ".join(tags) if tags else "state")


async def run_deer_execution(
    *,
    pool: asyncpg.Pool,
    settings: Settings,
    stream_hub: ExecutionStreamHub,
    checkpointer: Any,
    execution_id: UUID,
    workspace_id: UUID,
    agent_id: UUID,
    user_id: UUID,
    user_message: str,
    agent_config: dict[str, Any] | None = None,
    schedule_id: str | None = None,
    store: Any | None = None,
) -> None:
    repo = FlowRepository(pool)
    cfg = dict(agent_config) if isinstance(agent_config, dict) else {}
    _template = cfg.get("template") or (cfg.get("graph") or {}).get("template", "unknown") or "unknown"
    thread_id = await repo.get_thread_id(execution_id) or execution_id
    ctx = GraphContext(
        pool=pool,
        workspace_id=workspace_id,
        agent_id=agent_id,
        user_id=user_id,
        openai_api_key=settings.openai_api_key,
        agent_config=cfg,
        anthropic_api_key=settings.anthropic_api_key,
        execution_id=execution_id,
        settings=settings,
        stream_hub=stream_hub,
        store=store,
    )
    graph = build_agent_from_ctx(ctx, checkpointer=checkpointer)
    config: dict[str, Any] = {
        "configurable": {"thread_id": str(thread_id)},
        "metadata": {
            "execution_id": str(execution_id),
            "agent_id": str(agent_id),
            "workspace_id": str(workspace_id),
            "user_id": str(user_id),
            "template": _template,
        },
        "tags": ["flow", "deer-flow", f"template:{_template}"],
        "run_name": f"flow-exec-{execution_id}",
    }
    initial: dict[str, Any] = {"messages": [HumanMessage(content=user_message)]}

    debug_chunks = settings.log_level.strip().upper() == "DEBUG"
    _t_start = _time.monotonic()
    _exec_status = "completed"
    try:
        _log_banner(
            logger,
            "execution.start ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            template=_template,
            message_chars=len(user_message),
        )
        async for mode, chunk in graph.astream(initial, config, stream_mode=["updates", "messages"]):
            if debug_chunks:
                preview = repr(chunk)
                if len(preview) > 800:
                    preview = preview[:800] + "…"
                logger.debug(
                    "execution.stream_chunk",
                    execution_id=str(execution_id),
                    mode=mode,
                    chunk_preview=preview,
                )
            if mode == "updates":
                for node_name, partial in chunk.items():
                    payload = _json_safe({"node": node_name, "partial": partial})
                    await repo.insert_event(execution_id, "node_update", payload)
                    stream_hub.publish(
                        execution_id,
                        {
                            "kind": "node_update",
                            "node": node_name,
                            "summary": _summarize_node_partial(node_name, partial),
                            "payload": payload,
                        },
                    )
            elif mode == "messages":
                msg_chunk, metadata = chunk
                content = getattr(msg_chunk, "content", None)
                if isinstance(content, str) and content:
                    node_name = metadata.get("langgraph_node", "") if isinstance(metadata, dict) else ""
                    await repo.insert_event(execution_id, "token", {"text": content, "node": node_name})
                    stream_hub.publish(execution_id, {"kind": "token", "text": content, "node": node_name})

        ags = getattr(graph, "aget_state", None)
        if callable(ags):
            snap = await ags(config)
        else:
            snap = graph.get_state(config)
        values = snap.values if snap else {}
        answer = values.get("answer") or ""
        confidence = float(values.get("confidence") or 0.8)

        await repo.insert_event(execution_id, "final", {"answer": str(answer), "confidence": confidence})
        stream_hub.publish(execution_id, {"kind": "final", "answer": str(answer), "confidence": confidence})

        rag_sources = values.get("rag_sources") or []
        if rag_sources:
            await repo.insert_event(execution_id, "citations", {"citations": rag_sources})
            stream_hub.publish(execution_id, {"kind": "citations", "payload": rag_sources})

        await repo.complete_execution(execution_id, "completed", None)

        # Webhook delivery for scheduled runs
        if schedule_id:
            _delivery = await _get_schedule_delivery(pool, schedule_id)
            if _delivery and _delivery["type"] == "webhook" and _delivery["target"]:
                await _fire_webhook(
                    url=_delivery["target"],
                    execution_id=str(execution_id),
                    agent_id=str(agent_id),
                    answer=str(answer)[:4000],
                )

        _duration_ms = int((_time.monotonic() - _t_start) * 1000)
        _log_banner(
            logger,
            "execution.done  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            duration_ms=_duration_ms,
            confidence=round(confidence, 3),
            answer_chars=len(str(answer)),
            template=_template,
        )

    except Exception as exc:
        _duration_ms = int((_time.monotonic() - _t_start) * 1000)
        logger.error(
            "execution.failed ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            duration_ms=_duration_ms,
            error=str(exc),
            template=_template,
            exc_info=True,
        )
        await repo.insert_event(execution_id, "error", {"message": str(exc)})
        stream_hub.publish(execution_id, {"kind": "error", "message": str(exc)})
        _exec_status = "failed"
        await repo.complete_execution(execution_id, "failed", str(exc))
    finally:
        try:
            async with pool.acquire() as conn:
                skill_rows = await conn.fetch(
                    "SELECT payload->>'skill_id' AS skill_id FROM execution_events "
                    "WHERE execution_id=$1 AND kind='skill_invoked'",
                    execution_id,
                )
            skill_ids = [
                UUID(r["skill_id"]) for r in skill_rows if r["skill_id"]
            ]
            await _index_execution(
                pool,
                workspace_id=workspace_id,
                agent_id=agent_id,
                execution_id=execution_id,
                status=_exec_status,
                skill_ids=skill_ids,
            )
        except Exception:
            pass
        stream_hub.publish(execution_id, {"kind": "done"})
