from __future__ import annotations

import json
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


def _json_safe(obj: Any) -> Any:
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        if isinstance(obj, dict):
            return {k: _json_safe(v) for k, v in obj.items()}
        return str(obj)


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
    )
    graph = build_deer_flow_graph(ctx, checkpointer=checkpointer)
    config = {"configurable": {"thread_id": str(execution_id)}}
    initial: dict[str, Any] = {"messages": [HumanMessage(content=user_message)]}

    try:
        async for mode, chunk in graph.astream(initial, config, stream_mode=["updates", "messages"]):
            if mode == "updates":
                for node_name, partial in chunk.items():
                    payload = _json_safe({"node": node_name, "partial": partial})
                    await repo.insert_event(execution_id, "node_update", payload)
                    stream_hub.publish(
                        execution_id,
                        {"kind": "node_update", "node": node_name, "payload": payload},
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
        await repo.complete_execution(execution_id, "completed", None)

        # Save episodic memory: 1-sentence run summary
        if answer and settings.openai_api_key:
            try:
                from flow.infrastructure.llm import embeddings as emb_svc
                summary = answer[:500]
                emb = (await emb_svc.embed_texts(api_key=settings.openai_api_key, texts=[summary]))[0]
                await repo.insert_episodic_memory(
                    workspace_id, agent_id, user_id, summary, emb, execution_id=execution_id
                )
            except Exception:
                pass  # episodic save is best-effort
    except Exception as exc:
        logger.exception("execution.failed", execution_id=str(execution_id))
        await repo.insert_event(execution_id, "error", {"message": str(exc)})
        stream_hub.publish(execution_id, {"kind": "error", "message": str(exc)})
        await repo.complete_execution(execution_id, "failed", str(exc))
    finally:
        stream_hub.publish(execution_id, {"kind": "done"})
