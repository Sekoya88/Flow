from __future__ import annotations

from typing import Any

from flow.infrastructure.agentic_rag.audit import save_rag_audit
from flow.infrastructure.agentic_rag.graph import AgenticState, build_agentic_retrieval_graph
from flow.infrastructure.graph.deer_graph import GraphContext


async def run_agentic_retrieval(ctx: GraphContext, user_text: str) -> tuple[list[str], dict[str, Any]]:
    """Runs LangGraph retrieval pipeline and persists audit row."""
    graph = build_agentic_retrieval_graph(ctx)
    initial: AgenticState = {
        "query_original": user_text,
        "query_current": user_text,
        "sub_queries": [],
        "retrieved_docs": [],
        "graded_docs": [],
        "web_results": [],
        "routing_decision": "",
        "dense_retrieval": False,
        "iteration_count": 1,
        "max_iterations": 3,
        "rag_bits": [],
        "web_fallback_used": False,
        "explanation": {
            "reasoning_steps": [],
            "retrieval_queries": [],
            "documents_retrieved": 0,
            "documents_after_grading": 0,
            "documents_used_in_answer": 0,
            "citations": [],
            "confidence_score": 0.0,
            "fallback_used": False,
            "iterations": 1,
            "routing_decision": "",
            "latency": {},
        },
    }
    final = await graph.ainvoke(initial)
    rag_bits = list(final.get("rag_bits") or [])
    explanation = dict(final.get("explanation") or {})
    cs = explanation.get("confidence_score")

    await save_rag_audit(
        ctx.pool,
        execution_id=ctx.execution_id,
        workspace_id=ctx.workspace_id,
        query_original=user_text,
        query_rewritten=str(final.get("query_current") or user_text),
        routing_decision=str(explanation.get("routing_decision") or final.get("routing_decision") or ""),
        iteration_count=int(final.get("iteration_count") or 1),
        fallback_used=bool(explanation.get("fallback_used")),
        confidence_score=float(cs) if cs is not None else None,
        latency_ms=dict(explanation.get("latency") or {}),
        explanation=explanation,
        citations=list(explanation.get("citations") or []),
    )

    return rag_bits, explanation
