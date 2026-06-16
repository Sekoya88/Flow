from __future__ import annotations

import json
import time as _time
from typing import Any
from uuid import UUID

import asyncpg
from langchain_core.messages import HumanMessage

from flow.config import Settings
from flow.infrastructure.execution_streams import ExecutionEventEmitter, ExecutionStreamHub
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
            await client.post(
                url,
                json={
                    "execution_id": execution_id,
                    "agent_id": agent_id,
                    "answer": answer,
                },
            )
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


async def _apply_rubric_loop(
    ctx: GraphContext,
    emitter: ExecutionEventEmitter,
    execution_id: UUID,
    user_message: str,
    answer: str,
    rubric: dict[str, Any],
) -> str:
    """deepagents-style rubric runtime: evaluate the answer against rubric criteria
    and iterate (evaluate → refine) until satisfied or max_iterations is reached.

    Configured via agent_config["rubric"] = {"criteria": [...], "max_iterations": 2}.
    Emits persisted `rubric_evaluation_start` / `rubric_evaluation_end` events so the
    run UI can show the loop.
    """
    from langchain_core.messages import SystemMessage

    from flow.infrastructure.graph.nodes import _get_llm

    criteria = [str(c).strip() for c in (rubric.get("criteria") or []) if str(c).strip()]
    if not criteria or not answer:
        return answer
    llm = _get_llm(ctx)
    if llm is None:
        return answer
    try:
        max_iters = max(1, min(int(rubric.get("max_iterations", 2)), 3))
    except (TypeError, ValueError):
        max_iters = 2

    crit_block = "\n".join(f"- {c}" for c in criteria)
    for iteration in range(1, max_iters + 1):
        await emitter.emit(
            execution_id,
            "rubric_evaluation_start",
            {"iteration": iteration, "criteria_count": len(criteria)},
        )
        satisfied = True
        feedback = ""
        try:
            out = await llm.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "You are a strict rubric evaluator. Judge whether the answer satisfies "
                            "EVERY criterion. Output ONLY valid JSON: "
                            '{"satisfied": <bool>, "feedback": "<what to fix, empty if satisfied>"}'
                        )
                    ),
                    HumanMessage(content=(f"Criteria:\n{crit_block}\n\nUser request:\n{user_message[:1500]}\n\nAnswer:\n{str(answer)[:6000]}")),
                ]
            )
            raw = str(out.content).strip()
            if "```" in raw:
                raw = raw.split("```")[1].removeprefix("json").strip()
            data = json.loads(raw)
            satisfied = bool(data.get("satisfied"))
            feedback = str(data.get("feedback") or "")
        except Exception as exc:
            logger.warning("rubric.evaluation_failed", error=str(exc))
            await emitter.emit(
                execution_id,
                "rubric_evaluation_end",
                {"iteration": iteration, "satisfied": True, "error": str(exc)[:500]},
            )
            return answer

        await emitter.emit(
            execution_id,
            "rubric_evaluation_end",
            {"iteration": iteration, "satisfied": satisfied, "feedback": feedback[:1000]},
        )
        if satisfied or iteration == max_iters:
            return answer

        try:
            refined = await llm.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "Rewrite the answer so it satisfies all rubric criteria, keeping what "
                            "was already correct. Output only the improved answer."
                        )
                    ),
                    HumanMessage(
                        content=(
                            f"Criteria:\n{crit_block}\n\nEvaluator feedback:\n{feedback[:2000]}\n\n"
                            f"User request:\n{user_message[:1500]}\n\nCurrent answer:\n{str(answer)[:6000]}"
                        )
                    ),
                ]
            )
            new_answer = str(refined.content).strip()
            if new_answer:
                answer = new_answer
        except Exception as exc:
            logger.warning("rubric.refine_failed", error=str(exc))
            return answer
    return answer


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
    emitter = ExecutionEventEmitter(stream_hub, pool)
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
    if graph is None:
        err = "No LLM configured — set FLOW_OPENAI_API_KEY or FLOW_ANTHROPIC_API_KEY in the environment."
        await emitter.emit(execution_id, "error", {"message": err})
        await repo.complete_execution(execution_id, "failed", err)
        return
    from flow.infrastructure.observability.callbacks import FlowCallbackHandler

    _flow_cb = FlowCallbackHandler(
        workspace_id=str(workspace_id),
        agent_id=str(agent_id),
        execution_id=str(execution_id),
        template=_template,
        emitter=emitter,
    )
    config: dict[str, Any] = {
        "configurable": {"thread_id": str(thread_id)},
        "callbacks": [_flow_cb],
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
        # Per-node text buffers: token deltas stream live-only over Redis; the
        # aggregated text is persisted once per node as a `message` event so
        # backfill/replay reconstruct the same timeline without one DB row per token.
        _node_text: dict[str, list[str]] = {}

        async def _flush_message(node_name: str) -> None:
            parts = _node_text.pop(node_name, None)
            if parts:
                await emitter.emit(execution_id, "message", {"node": node_name, "text": "".join(parts)})

        async for mode, chunk in graph.astream(initial, config, stream_mode=["updates", "messages", "custom"]):
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
                    await _flush_message(node_name)
                    payload = _json_safe({"node": node_name, "partial": partial})
                    await emitter.emit(
                        execution_id,
                        "node_update",
                        {
                            "node": node_name,
                            "summary": _summarize_node_partial(node_name, partial),
                            "payload": payload,
                        },
                    )
            elif mode == "messages":
                msg_chunk, metadata = chunk
                content = getattr(msg_chunk, "content", None)
                if isinstance(content, str) and content:
                    meta = metadata if isinstance(metadata, dict) else {}
                    node_name = meta.get("langgraph_node", "")
                    # Tag token provenance (e.g. lc_source == "summarization" per the
                    # deepagents context-engineering guidance) so the UI can badge it.
                    source = meta.get("lc_source") or ""
                    token_payload: dict[str, Any] = {"text": content, "node": node_name}
                    if source:
                        token_payload["source"] = source
                    else:
                        _node_text.setdefault(node_name, []).append(content)
                    await emitter.emit(execution_id, "token", token_payload, persist=False)
            elif mode == "custom":
                # Passthrough for get_stream_writer() events emitted inside nodes
                # (tool deltas, rubric evaluations, progress). Live-only by default;
                # a node opts into persistence with {"persist": true}.
                if isinstance(chunk, dict):
                    ev = dict(chunk)
                    kind = str(ev.pop("kind", "custom"))
                    persist = bool(ev.pop("persist", False))
                    await emitter.emit(execution_id, kind, _json_safe(ev), persist=persist)

        for _pending_node in list(_node_text):
            await _flush_message(_pending_node)

        ags = getattr(graph, "aget_state", None)
        if callable(ags):
            snap = await ags(config)
        else:
            snap = graph.get_state(config)
        values = snap.values if snap else {}
        answer = values.get("answer") or ""
        confidence = float(values.get("confidence") or 0.8)

        # Fallback: agents that stream tokens but don't set an explicit "answer"
        # state key (e.g. ReAct/tool agents) — use last AIMessage content.
        if not answer:
            msgs = values.get("messages") or []
            for msg in reversed(msgs):
                content = getattr(msg, "content", "")
                if content and getattr(msg, "type", "") == "ai":
                    answer = content if isinstance(content, str) else str(content)
                    break

        # Rubric runtime (deepagents-inspired): iterate evaluate → refine when the
        # agent config declares a rubric. Best-effort — never fails the run.
        _rubric = cfg.get("rubric")
        if isinstance(_rubric, dict) and answer:
            try:
                answer = await _apply_rubric_loop(ctx, emitter, execution_id, user_message, str(answer), _rubric)
            except Exception:
                logger.warning("rubric.loop_failed", exc_info=True)

        await emitter.emit(execution_id, "final", {"answer": str(answer), "confidence": confidence})

        rag_sources = values.get("rag_sources") or []
        if rag_sources:
            await emitter.emit(execution_id, "citations", {"citations": rag_sources, "payload": rag_sources})

        await repo.complete_execution(execution_id, "completed", None)

        # Bridge → episodic_memories: write a searchable Q+A summary after each run
        try:
            summary = f"Q: {user_message[:400]}\n\nA: {str(answer)[:800]}"
            _ep_emb = None
            if settings.openai_api_key:
                from flow.infrastructure.llm import embeddings as _emb_svc

                _ep_emb = (await _emb_svc.embed_texts(api_key=settings.openai_api_key, texts=[summary]))[0]
            await repo.insert_episodic_memory(
                workspace_id, agent_id, user_id, summary, _ep_emb, execution_id=execution_id
            )
        except Exception:
            pass

        # Auto-trigger curator on low-confidence runs (skip scheduled deliveries)
        if confidence < 0.7 and not schedule_id:
            try:
                from flow.application.curator import maybe_spawn_proposal

                await maybe_spawn_proposal(
                    repo=repo,
                    workspace_id=workspace_id,
                    agent_id=agent_id,
                    user_id=user_id,
                    execution_id=execution_id,
                    score=confidence,
                    openai_api_key=settings.openai_api_key,
                )
            except Exception:
                pass

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
        try:
            from flow.infrastructure.observability.metrics import record_execution

            record_execution(_template, "completed", _duration_ms / 1000)
        except Exception:
            pass

    except Exception as exc:
        _duration_ms = int((_time.monotonic() - _t_start) * 1000)
        logger.error(
            "execution.failed ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            duration_ms=_duration_ms,
            error=str(exc),
            template=_template,
            exc_info=True,
        )
        await emitter.emit(execution_id, "error", {"message": str(exc)})
        _exec_status = "failed"
        await repo.complete_execution(execution_id, "failed", str(exc))
        try:
            from flow.infrastructure.observability.metrics import record_execution

            record_execution(_template, "failed", _duration_ms / 1000)
        except Exception:
            pass
    finally:
        try:
            async with pool.acquire() as conn:
                skill_rows = await conn.fetch(
                    "SELECT payload->>'skill_id' AS skill_id FROM execution_events WHERE execution_id=$1 AND kind='skill_invoked'",
                    execution_id,
                )
            skill_ids = [UUID(r["skill_id"]) for r in skill_rows if r["skill_id"]]
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
