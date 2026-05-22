from __future__ import annotations

import asyncio
import time
from typing import Any, Literal

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from flow.infrastructure.agentic_rag.context_pack import build_rag_messages, flow_kb_label
from flow.infrastructure.agentic_rag.models import DocumentGrade, RoutingDecision
from flow.infrastructure.agentic_rag.prompts import GRADER_PROMPT, REWRITER_PROMPT, SUPERVISOR_PROMPT
from flow.infrastructure.agentic_rag.qdrant_hybrid import (
    dense_search_async,
    get_qdrant_client,
    hybrid_search_rrf_async,
    setup_collection,
    sparse_encode_text,
)
from flow.infrastructure.graph.deer_graph import GraphContext
from flow.infrastructure.llm import embeddings as emb_svc
from flow.infrastructure.observability.logging import get_logger

log = get_logger("flow.agentic_rag")

_ALLOWED_ROUTING = frozenset({"RETRIEVE_HYBRID", "RETRIEVE_DENSE", "WEB_SEARCH", "DIRECT_ANSWER", "MULTI_HOP"})


class AgenticState(TypedDict, total=False):
    query_original: str
    query_current: str
    sub_queries: list[str]
    retrieved_docs: list[dict[str, Any]]
    graded_docs: list[dict[str, Any]]
    web_results: list[str]
    routing_decision: str
    dense_retrieval: bool
    iteration_count: int
    max_iterations: int
    rag_bits: list[str]
    web_fallback_used: bool
    explanation: dict[str, Any]


def _normalize_routing(raw: str) -> str:
    u = (raw or "").strip().upper()
    if u in _ALLOWED_ROUTING:
        return u
    return "RETRIEVE_HYBRID"


def _exp_blob(state: AgenticState) -> dict[str, Any]:
    return dict(state.get("explanation") or {})


def route_supervisor(state: AgenticState) -> Literal["retrieve", "web_search", "assemble_direct"]:
    d = state.get("routing_decision", "")
    if d == "DIRECT_ANSWER":
        return "assemble_direct"
    if d == "WEB_SEARCH":
        return "web_search"
    return "retrieve"


def route_after_grade(state: AgenticState) -> Literal["assemble", "rewrite", "web_fallback"]:
    if state.get("graded_docs"):
        return "assemble"
    if int(state.get("iteration_count") or 1) >= int(state.get("max_iterations") or 3):
        return "web_fallback"
    return "rewrite"


def build_agentic_retrieval_graph(ctx: GraphContext):
    settings = ctx.settings
    if settings is None or not settings.qdrant_url:
        raise ValueError("agentic_rag requires GraphContext.settings.qdrant_url")

    qdrant_url = settings.qdrant_url.strip().rstrip("/")
    collection = settings.qdrant_collection
    client = get_qdrant_client(qdrant_url if qdrant_url.startswith("http") else f"http://{qdrant_url}")

    async def supervisor_node(state: AgenticState) -> dict[str, Any]:
        t0 = time.perf_counter()
        exp = _exp_blob(state)
        prev = f"previous routing: {state.get('routing_decision', '')}" if int(state.get("iteration_count") or 1) > 1 else "first attempt"
        prompt = SUPERVISOR_PROMPT.format(
            query=state.get("query_current", ""),
            iteration=state.get("iteration_count", 1),
            max_iterations=state.get("max_iterations", 3),
            previous_context=prev,
        )
        decision = "RETRIEVE_HYBRID"
        reasoning = "default"
        sub_queries: list[str] = []
        confidence = 0.8
        if ctx.openai_api_key:
            try:
                llm = ChatOpenAI(api_key=ctx.openai_api_key, model="gpt-5.4-mini", temperature=0)
                structured = llm.with_structured_output(RoutingDecision)
                out = await structured.ainvoke([HumanMessage(content=prompt)])
                if isinstance(out, RoutingDecision):
                    decision = _normalize_routing(out.decision)
                    reasoning = out.reasoning or ""
                    sub_queries = list(out.sub_queries or [])
                    confidence = float(out.confidence)
            except Exception:
                pass
        dense_retrieval = decision == "RETRIEVE_DENSE"
        steps = list(exp.get("reasoning_steps") or [])
        steps.append(f"iter {state.get('iteration_count', 1)}: {decision} — {reasoning}")
        lat = dict(exp.get("latency") or {})
        lat["supervisor_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        exp.update(
            {
                "reasoning_steps": steps,
                "routing_decision": decision,
                "latency": lat,
                "supervisor_confidence": confidence,
            }
        )
        log.info(
            "agentic_rag.supervisor",
            decision=decision,
            confidence=round(confidence, 3),
            ms=lat["supervisor_ms"],
            workspace_id=str(ctx.workspace_id),
        )
        return {
            "routing_decision": decision,
            "sub_queries": sub_queries,
            "dense_retrieval": dense_retrieval,
            "explanation": exp,
        }

    async def retrieve_node(state: AgenticState) -> dict[str, Any]:
        t0 = time.perf_counter()
        exp = _exp_blob(state)
        queries = [state.get("query_current", "")]
        sq = state.get("sub_queries") or []
        if state.get("routing_decision") == "MULTI_HOP" and sq:
            queries = [state.get("query_current", "")] + sq

        all_docs: dict[str, dict[str, Any]] = {}
        if not ctx.openai_api_key:
            lat = dict(exp.get("latency") or {})
            lat["retriever_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            exp.update({"documents_retrieved": 0, "latency": lat})
            return {"retrieved_docs": [], "explanation": exp}
        try:
            await asyncio.to_thread(setup_collection, client, collection)
            for q in queries:
                q = (q or "").strip()
                if not q:
                    continue
                sparse_i, sparse_v = await sparse_encode_text(q)
                dense = (await emb_svc.embed_texts(api_key=ctx.openai_api_key, texts=[q]))[0]
                if state.get("dense_retrieval"):
                    docs = await dense_search_async(
                        client,
                        collection=collection,
                        workspace_id=ctx.workspace_id,
                        dense_vector=dense,
                        limit=8,
                    )
                else:
                    docs = await hybrid_search_rrf_async(
                        client,
                        collection=collection,
                        workspace_id=ctx.workspace_id,
                        dense_vector=dense,
                        sparse_indices=sparse_i,
                        sparse_values=sparse_v,
                        limit=8,
                    )
                for doc in docs:
                    cid = doc["chunk_id"]
                    if cid not in all_docs or doc["score"] > all_docs[cid]["score"]:
                        all_docs[cid] = doc
            retrieved = sorted(all_docs.values(), key=lambda x: x["score"], reverse=True)
        except Exception:
            log.warning("agentic_rag.retrieve_failed", workspace_id=str(ctx.workspace_id))
            retrieved = []

        rq = list(exp.get("retrieval_queries") or [])
        for q in queries:
            if q and q not in rq:
                rq.append(q)
        lat = dict(exp.get("latency") or {})
        lat["retriever_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        exp.update({"retrieval_queries": rq, "documents_retrieved": len(retrieved), "latency": lat})
        log.info(
            "agentic_rag.retrieve",
            mode="dense" if state.get("dense_retrieval") else "hybrid_rrf",
            chunks=len(retrieved),
            ms=lat["retriever_ms"],
            workspace_id=str(ctx.workspace_id),
        )
        return {"retrieved_docs": retrieved, "explanation": exp}

    async def grade_node(state: AgenticState) -> dict[str, Any]:
        t0 = time.perf_counter()
        exp = _exp_blob(state)
        graded: list[dict[str, Any]] = []
        if not ctx.openai_api_key:
            graded = list(state.get("retrieved_docs") or [])
        else:
            llm = ChatOpenAI(api_key=ctx.openai_api_key, model="gpt-5.4-mini", temperature=0)
            structured = llm.with_structured_output(DocumentGrade)
            for doc in state.get("retrieved_docs") or []:
                try:
                    prompt = GRADER_PROMPT.format(
                        question=state.get("query_original", ""),
                        chunk_id=doc.get("chunk_id", ""),
                        document=str(doc.get("content", ""))[:1500],
                        source=str((doc.get("metadata") or {}).get("source", "unknown")),
                    )
                    g = await structured.ainvoke([HumanMessage(content=prompt)])
                    if isinstance(g, DocumentGrade) and g.combined_score >= 0.6:
                        gd = dict(g.model_dump())
                        gd["combined_score"] = g.combined_score
                        graded.append({**doc, "grade": gd})
                except Exception:
                    continue
        graded.sort(
            key=lambda x: float((x.get("grade") or {}).get("combined_score", 0.0)),
            reverse=True,
        )
        lat = dict(exp.get("latency") or {})
        lat["grader_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        exp.update({"documents_after_grading": len(graded), "latency": lat})
        log.info(
            "agentic_rag.grade",
            kept=len(graded),
            retrieved=len(state.get("retrieved_docs") or []),
            ms=lat["grader_ms"],
        )
        return {"graded_docs": graded, "explanation": exp}

    async def rewriter_node(state: AgenticState) -> dict[str, Any]:
        t0 = time.perf_counter()
        exp = _exp_blob(state)
        attempt = int(state.get("iteration_count") or 1)
        prompt = REWRITER_PROMPT.format(
            query=state.get("query_current", ""),
            failure_reason=(
                f"only {len(state.get('graded_docs') or [])} relevant chunks after grading from {len(state.get('retrieved_docs') or [])} retrieved."
            ),
            attempt=attempt,
            max_attempts=state.get("max_iterations", 3),
        )
        new_q = state.get("query_current", "")
        if ctx.openai_api_key:
            try:
                llm = ChatOpenAI(api_key=ctx.openai_api_key, model="gpt-5.4-mini", temperature=0.2)
                out = await llm.ainvoke([HumanMessage(content=prompt)])
                new_q = str(out.content).strip()
            except Exception:
                pass
        rq = list(exp.get("retrieval_queries") or [])
        if new_q and new_q not in rq:
            rq.append(new_q)
        next_iter = attempt + 1
        lat = dict(exp.get("latency") or {})
        lat["rewriter_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        exp.update({"retrieval_queries": rq, "iterations": next_iter, "latency": lat})
        log.info("agentic_rag.rewrite", iteration=next_iter, ms=lat["rewriter_ms"])
        return {
            "query_current": new_q,
            "iteration_count": next_iter,
            "explanation": exp,
        }

    async def web_search_node(state: AgenticState) -> dict[str, Any]:
        t0 = time.perf_counter()
        exp = _exp_blob(state)
        results: list[str] = []
        key = settings.tavily_api_key if settings else None
        if key:
            try:

                def _run() -> list[str]:
                    from tavily import TavilyClient

                    tc = TavilyClient(api_key=key)
                    r = tc.search(state.get("query_current", ""), max_results=5)
                    return [str(x.get("content", "")) for x in (r.get("results") or []) if x.get("content")]

                results = await asyncio.to_thread(_run)
            except Exception:
                results = []
        lat = dict(exp.get("latency") or {})
        lat["web_search_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        exp["latency"] = lat
        log.info("agentic_rag.web_search", hits=len(results), ms=lat["web_search_ms"])
        return {"web_results": results, "explanation": exp}

    async def web_fallback_node(state: AgenticState) -> dict[str, Any]:
        exp = _exp_blob(state)
        exp["reasoning_steps"] = list(exp.get("reasoning_steps") or []) + ["max iterations reached — web fallback"]
        return {"web_fallback_used": True, "explanation": exp}

    async def assemble_node(state: AgenticState) -> dict[str, Any]:
        exp = _exp_blob(state)
        bits = build_rag_messages(
            graded_docs=list(state.get("graded_docs") or []),
            web_results=list(state.get("web_results") or []),
        )
        log.info(
            "agentic_rag.assemble",
            graded=len(state.get("graded_docs") or []),
            web=len(state.get("web_results") or []),
        )
        return {"rag_bits": bits, "explanation": exp}

    async def assemble_direct_node(state: AgenticState) -> dict[str, Any]:
        exp = _exp_blob(state)
        exp["documents_retrieved"] = 0
        exp["documents_after_grading"] = 0
        steps = list(exp.get("reasoning_steps") or [])
        steps.append("supervisor: DIRECT_ANSWER — skipped retrieval")
        exp["reasoning_steps"] = steps
        return {
            "rag_bits": ["[agentic_rag] Supervisor chose DIRECT_ANSWER — no knowledge retrieval context."],
            "explanation": exp,
        }

    async def finalize_node(state: AgenticState) -> dict[str, Any]:
        t0 = time.perf_counter()
        exp = _exp_blob(state)
        graded = list(state.get("graded_docs") or [])
        rag_joined = "\n".join(state.get("rag_bits") or [])
        citations: list[dict[str, Any]] = []
        for i, doc in enumerate(graded, 1):
            label = flow_kb_label(i)
            grade = doc.get("grade") or {}
            meta = doc.get("metadata") or {}
            excerpt = str(doc.get("content", ""))[:200]
            rel = float(grade.get("thematic_score", 0.0))
            used = f"[{label}]" in rag_joined
            citations.append(
                {
                    "chunk_id": str(doc.get("chunk_id", "")),
                    "source_url": str(meta.get("source", "") or ""),
                    "source_title": str(meta.get("title", "") or ""),
                    "page_number": meta.get("page"),
                    "excerpt": excerpt,
                    "relevance_score": rel,
                    "used_in_answer": used,
                }
            )
        used_scores = [c["relevance_score"] for c in citations if c.get("used_in_answer")]
        if used_scores:
            confidence = round(sum(used_scores) / len(used_scores), 3)
        elif graded:
            confidence = round(
                sum(float((d.get("grade") or {}).get("thematic_score", 0.0)) for d in graded) / len(graded),
                3,
            )
        else:
            confidence = 0.25
        lat = dict(exp.get("latency") or {})
        lat["finalize_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        lat["total_ms"] = round(sum(v for v in lat.values() if isinstance(v, (int, float))), 2)
        exp.update(
            {
                "citations": citations,
                "confidence_score": confidence,
                "documents_used_in_answer": sum(1 for c in citations if c.get("used_in_answer")),
                "fallback_used": bool(state.get("web_fallback_used")),
                "iterations": int(state.get("iteration_count") or 1),
                "routing_decision": state.get("routing_decision", ""),
                "latency": lat,
            }
        )
        log.info(
            "agentic_rag.finalize",
            confidence=confidence,
            total_ms=lat["total_ms"],
            citations=len(citations),
            execution_id=str(ctx.execution_id) if ctx.execution_id else None,
        )
        return {"explanation": exp}

    workflow = StateGraph(AgenticState)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("grade_documents", grade_node)
    workflow.add_node("rewrite_question", rewriter_node)
    workflow.add_node("web_fallback_flag", web_fallback_node)
    workflow.add_node("web_search", web_search_node)
    workflow.add_node("assemble", assemble_node)
    workflow.add_node("assemble_direct", assemble_direct_node)
    workflow.add_node("finalize", finalize_node)

    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {"retrieve": "retrieve", "web_search": "web_search", "assemble_direct": "assemble_direct"},
    )
    workflow.add_edge("retrieve", "grade_documents")
    workflow.add_conditional_edges(
        "grade_documents",
        route_after_grade,
        {"assemble": "assemble", "rewrite": "rewrite_question", "web_fallback": "web_fallback_flag"},
    )
    workflow.add_edge("rewrite_question", "supervisor")
    workflow.add_edge("web_fallback_flag", "web_search")
    workflow.add_edge("web_search", "assemble")
    workflow.add_edge("assemble", "finalize")
    workflow.add_edge("assemble_direct", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile()
