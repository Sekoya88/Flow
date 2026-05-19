from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict
from uuid import UUID

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from flow.infrastructure.llm.embeddings import embed_texts


@dataclass
class QueryConfig:
    workspace_id: UUID
    repo: Any  # FlowRepository
    engine: Any  # KGGraphEngine
    openai_api_key: str


class QueryState(TypedDict):
    question: str
    tool_calls: list[dict]
    graph_path: list[str] | None
    graph_path_edges: list[str] | None
    cited_node_ids: list[str]
    context_chunks: list[str]
    answer: str | None


def build_kg_query_graph(config: QueryConfig):
    """Build and compile the KG query ReAct-style LangGraph."""

    repo = config.repo
    engine = config.engine
    workspace_id = config.workspace_id
    api_key = config.openai_api_key

    def _llm() -> ChatOpenAI:
        return ChatOpenAI(model="gpt-4o-mini", temperature=0.2, openai_api_key=api_key)

    # ── Tool helpers ─────────────────────────────────────────────────────────

    async def _vector_search(query: str, k: int = 6) -> list[dict]:
        try:
            embs = await embed_texts(api_key=api_key, texts=[query])
            rows = await repo.vector_search_kg(workspace_id, embs[0], k=k)
            return [
                {
                    "id": str(r["id"]),
                    "label": r["label"],
                    "summary": r.get("summary") or "",
                    "node_type": r["node_type"],
                    "source_path": r.get("source_path"),
                }
                for r in rows
            ]
        except Exception:
            return []

    async def _get_node_content(node_id: str) -> str:
        try:
            row = await repo.get_kg_node(UUID(node_id))
            if row is None:
                return ""
            return row.get("summary") or ""
        except Exception:
            return ""

    def _find_path(source_label: str, target_label: str, G) -> dict:
        try:
            labels, edges = engine.find_shortest_path_ids(G, source_label, target_label)
            return {"path": labels, "edges": edges}
        except Exception as e:
            return {"path": None, "error": str(e)}

    def _explore_subgraph(node_label: str, G, depth: int = 2) -> dict:
        try:
            sub = engine.get_subgraph(G, node_label, depth=depth)
            nodes = [{"label": sub.nodes[n]["label"], "pagerank": sub.nodes[n].get("pagerank", 0)} for n in sub.nodes]
            edges = [
                {"source": sub.nodes[e[0]]["label"], "target": sub.nodes[e[1]]["label"], "type": sub.edges[e].get("edge_type")} for e in sub.edges
            ]
            return {"nodes": nodes[:20], "edges": edges[:30]}
        except Exception:
            return {"nodes": [], "edges": []}

    def _get_cluster_summary(cluster_id: int, G) -> dict:
        try:
            nodes = engine.get_cluster_nodes(G, cluster_id)
            return {"cluster_id": cluster_id, "nodes": nodes[:20]}
        except Exception:
            return {"cluster_id": cluster_id, "nodes": []}

    # ── Node: gather context ─────────────────────────────────────────────────
    async def gather_context(state: QueryState) -> dict:
        question = state["question"]
        tool_calls: list[dict] = []
        context_chunks: list[str] = []
        cited_node_ids: list[str] = []
        graph_path: list[str] | None = None
        graph_path_edges: list[str] | None = None

        # Always do vector search
        tool_calls.append({"tool": "vector_search", "args": {"query": question}})
        results = await _vector_search(question, k=6)
        for r in results:
            cited_node_ids.append(r["id"])
            if r["summary"]:
                context_chunks.append(f"[{r['label']}] {r['summary']}")

        # Detect relational intent: "how does X relate to Y" / "path between"
        lower = question.lower()
        if any(kw in lower for kw in ["relate", "connect", "path", "between", "link"]):
            # Try to find two capitalized terms as source/target
            import re

            caps = re.findall(r"\b[A-Z][a-zA-Z]+\b", question)
            if len(caps) >= 2:
                try:
                    G = await engine.load_graph(workspace_id)
                    tool_calls.append({"tool": "find_path", "args": {"source": caps[0], "target": caps[-1]}})
                    path_result = _find_path(caps[0], caps[-1], G)
                    if path_result.get("path"):
                        graph_path = path_result["path"]
                        graph_path_edges = path_result.get("edges", [])
                        context_chunks.append(f"Path: {' → '.join(graph_path)}")
                except Exception:
                    pass

        # Detect exploratory intent: "what do i know", "explore", "summarize my notes"
        if any(kw in lower for kw in ["what do i know", "explore", "summarize my notes", "tell me about"]):
            if results:
                top_label = results[0]["label"]
                try:
                    G = await engine.load_graph(workspace_id)
                    tool_calls.append({"tool": "explore_subgraph", "args": {"node": top_label, "depth": 2}})
                    sub = _explore_subgraph(top_label, G, depth=2)
                    node_labels = [n["label"] for n in sub["nodes"][:10]]
                    context_chunks.append(f"Related concepts: {', '.join(node_labels)}")
                except Exception:
                    pass

        return {
            "tool_calls": tool_calls,
            "context_chunks": context_chunks,
            "cited_node_ids": cited_node_ids,
            "graph_path": graph_path,
            "graph_path_edges": graph_path_edges,
        }

    # ── Node: synthesize ─────────────────────────────────────────────────────
    async def synthesize(state: QueryState) -> dict:
        llm = _llm()
        context = "\n\n".join(state["context_chunks"]) or "No relevant notes found."
        path_info = ""
        if state.get("graph_path"):
            path_info = f"\nGraph path found: {' → '.join(state['graph_path'])}"

        prompt = f"""You are a knowledge graph assistant. Answer the user's question using their personal notes.
Be specific and cite which notes you're drawing from.

Question: {state["question"]}

Context from notes:
{context}{path_info}

Answer concisely (2-4 sentences). If a graph path was found, explain what it means."""

        try:
            resp = await llm.ainvoke(prompt)
            answer = resp.content
        except Exception:
            answer = "Unable to generate answer."

        return {"answer": answer}

    # ── Build graph ───────────────────────────────────────────────────────────
    builder = StateGraph(QueryState)
    builder.add_node("gather_context", gather_context)
    builder.add_node("synthesize", synthesize)

    builder.set_entry_point("gather_context")
    builder.add_edge("gather_context", "synthesize")
    builder.add_edge("synthesize", END)

    return builder.compile()
