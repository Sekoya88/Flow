from __future__ import annotations

import json
import time as _time
from typing import Any
from uuid import UUID

import asyncpg
from langchain_core.messages import HumanMessage

from flow.config import Settings
from flow.infrastructure.execution_streams import ExecutionStreamHub
from flow.infrastructure.graph.deer_graph import GraphContext, build_deer_flow_graph
from flow.infrastructure.observability.logging import get_logger
from flow.infrastructure.persistence.repo import FlowRepository

logger = get_logger(__name__)


def _log_banner(log, event: str, **kw) -> None:
    """Emit a structured log entry used as a visual execution delimiter in Docker logs."""
    log.info(event, **kw)


def _get_llm_for_judge(settings):
    """Get cheap LLM instance for post-run judge tasks."""
    if not settings.openai_api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(api_key=settings.openai_api_key, model="gpt-4o-mini", temperature=0)
    except Exception:
        return None


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
) -> None:
    repo = FlowRepository(pool)
    cfg = dict(agent_config) if isinstance(agent_config, dict) else {}
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
    )
    graph = build_deer_flow_graph(ctx, checkpointer=checkpointer)
    config: dict[str, Any] = {
        "configurable": {"thread_id": str(execution_id)},
        "metadata": {
            "execution_id": str(execution_id),
            "agent_id": str(agent_id),
            "workspace_id": str(workspace_id),
            "user_id": str(user_id),
        },
        "tags": ["flow", "deer-flow"],
        "run_name": f"flow-exec-{execution_id}",
    }
    initial: dict[str, Any] = {"messages": [HumanMessage(content=user_message)]}

    debug_chunks = settings.log_level.strip().upper() == "DEBUG"
    _t_start = _time.monotonic()
    _template = cfg.get("template") or (cfg.get("graph") or {}).get("template", "unknown") or "unknown"
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
        _duration_ms = int((_time.monotonic() - _t_start) * 1000)
        _log_banner(
            logger,
            "execution.done  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            duration_ms=_duration_ms,
            confidence=round(confidence, 3),
            answer_chars=len(str(answer)),
            template=_template,
        )

        # LLM-judge memory extraction (best-effort, post-run)
        if answer and settings.openai_api_key:
            try:
                from flow.infrastructure.llm import embeddings as emb_svc
                from flow.application.memory_judge import (
                    extract_facts_from_answer,
                    extract_pattern_summary,
                    should_store_pattern,
                )
                _judge_llm = _get_llm_for_judge(settings)
                _answer_str = str(answer)
                facts = await extract_facts_from_answer(_judge_llm, user_message, _answer_str) if _judge_llm else []
                for fact in facts:
                    emb = (await emb_svc.embed_texts(api_key=settings.openai_api_key, texts=[fact]))[0]
                    await repo.insert_episodic_memory(
                        workspace_id, agent_id, user_id, fact, emb, execution_id=execution_id
                    )
                if _judge_llm and await should_store_pattern(confidence, len(_answer_str)):
                    pattern = await extract_pattern_summary(_judge_llm, user_message, _answer_str)
                    if pattern:
                        problem_summary, solution_steps = pattern
                        pemb = (await emb_svc.embed_texts(api_key=settings.openai_api_key, texts=[problem_summary]))[0]
                        await repo.insert_reasoning_pattern(
                            workspace_id, agent_id, problem_summary, solution_steps, pemb, score=confidence
                        )
            except Exception:
                pass  # memory extraction is best-effort
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
        await repo.complete_execution(execution_id, "failed", str(exc))
    finally:
        stream_hub.publish(execution_id, {"kind": "done"})
