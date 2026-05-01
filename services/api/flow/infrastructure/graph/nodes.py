"""Node implementations for all graph templates.

Each node is a factory that captures GraphContext and returns an async callable
matching LangGraph's `(state) -> dict` signature.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.errors import NodeInterrupt

from flow.infrastructure.graph.state import FlowGraphState
from flow.infrastructure.llm import embeddings as emb_svc
from flow.infrastructure.persistence.repo import FlowRepository
from flow.infrastructure.tools.sandbox.factory import get_sandbox

if TYPE_CHECKING:
    from flow.infrastructure.graph.deer_graph import GraphContext


DEFAULT_TOOLS = {"retrieve": True, "sandbox": True, "long_term_memory": True}


def _resolved_tools(cfg: dict[str, Any]) -> dict[str, bool]:
    raw = cfg.get("tools") if isinstance(cfg.get("tools"), dict) else {}
    out = {**DEFAULT_TOOLS}
    for k in DEFAULT_TOOLS:
        if k in raw:
            out[k] = bool(raw[k])
    return out


def _get_llm(ctx: GraphContext):
    from flow.infrastructure.llm.providers import get_chat_model
    model_config = ctx.agent_config.get("model", {}) if ctx.agent_config else {}
    if not model_config:
        model_config = {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.2}
    return get_chat_model(
        model_config,
        fallback_api_keys={"openai": ctx.openai_api_key, "anthropic": ctx.anthropic_api_key},
    )


def _last_human_text(state: FlowGraphState) -> str:
    msgs = state.get("messages") or []
    last = next((m for m in reversed(msgs) if isinstance(m, HumanMessage)), None)
    return last.content if last else ""


async def _rag_and_memory(ctx: GraphContext, user_text: str, tools: dict[str, bool]):
    repo = FlowRepository(ctx.pool)
    rag_bits: list[str] = []
    mem_bits: list[str] = []
    settings = ctx.settings
    use_agentic = bool(
        tools["retrieve"]
        and ctx.openai_api_key
        and settings
        and settings.agentic_rag_enabled
        and settings.qdrant_url
        and settings.qdrant_url.strip()
    )
    if ctx.openai_api_key and (tools["retrieve"] or tools["long_term_memory"]):
        try:
            q_emb = (await emb_svc.embed_texts(api_key=ctx.openai_api_key, texts=[user_text]))[0]
            if tools["retrieve"]:
                try:
                    if use_agentic:
                        from flow.infrastructure.agentic_rag.pipeline import run_agentic_retrieval

                        rag_bits = (await run_agentic_retrieval(ctx, user_text))[0]
                    else:
                        rows = await repo.search_knowledge(ctx.workspace_id, q_emb, limit=4)
                        rag_bits = [r["content"] for r in rows]
                except Exception:
                    rows = await repo.search_knowledge(ctx.workspace_id, q_emb, limit=4)
                    rag_bits = [r["content"] for r in rows]
            if tools["long_term_memory"]:
                try:
                    mrows = await repo.search_memories(
                        ctx.workspace_id, ctx.agent_id, ctx.user_id, q_emb, limit=4
                    )
                    mem_bits = [r["content"] for r in mrows]
                except Exception:
                    pass
        except Exception:
            pass
    return rag_bits, mem_bits


# ---------------------------------------------------------------------------
# linear-3 / deer_flow nodes
# ---------------------------------------------------------------------------

def make_planner(ctx: GraphContext):
    from flow.infrastructure.observability.tracing import get_tracer
    tracer = get_tracer()

    async def planner(state: FlowGraphState) -> dict:
        with tracer.start_as_current_span("graph.planner") as span:
            span.set_attribute("execution.workspace_id", str(ctx.workspace_id))
            user_text = _last_human_text(state)
            llm = _get_llm(ctx)
            if llm is None:
                plan = "Offline plan: clarify goal, gather facts, draft answer."
            else:
                out = await llm.ainvoke([
                    SystemMessage(content="You are a planning node. Output a short numbered plan (max 5 bullets)."),
                    HumanMessage(content=user_text),
                ])
                plan = str(out.content)
            return {"plan": plan, "messages": [AIMessage(content=f"[planner]\n{plan}")]}

    return planner


def make_worker(ctx: GraphContext):
    from flow.infrastructure.observability.tracing import get_tracer
    tracer = get_tracer()
    tools = _resolved_tools(ctx.agent_config)
    repo = FlowRepository(ctx.pool)

    async def worker(state: FlowGraphState) -> dict:
        with tracer.start_as_current_span("graph.worker") as span:
            span.set_attribute("execution.workspace_id", str(ctx.workspace_id))
            plan = state.get("plan") or ""
            user_text = _last_human_text(state)
            rag_bits, mem_bits = await _rag_and_memory(ctx, user_text, tools)
            prefs = await repo.get_preferences(ctx.user_id)
            pref_lines = [f"{r['key']}: {r['value']}" for r in prefs[:20]]

            # Include agent negatives to avoid past mistakes
            neg_rows = await repo.list_agent_negatives(ctx.workspace_id, ctx.agent_id, limit=5)
            neg_bits = [r["content"] for r in neg_rows]

            rag_block = "\n---\n".join(rag_bits) or "(knowledge RAG disabled or no hits)"
            mem_block = "\n---\n".join(mem_bits) or "(long-term memory off or no hits)"
            pref_block = "\n".join(pref_lines) or "(no user preferences)"
            neg_block = "\n".join(f"- {n}" for n in neg_bits) or "(none)"

            llm = _get_llm(ctx)
            if llm is None:
                body = f"RAG:\n{rag_block}\n\nMemories:\n{mem_block}\n\nUser prefs:\n{pref_block}\n\nPlan:\n{plan}"
                return {"worker_output": body[:8000], "messages": [AIMessage(content=f"[worker]\n{body[:4000]}")]}

            out = await llm.ainvoke([
                SystemMessage(content=(
                    "You are a worker node. Use the plan, user message, retrieved snippets, "
                    "long-term memories, and preferences. Produce structured research notes. "
                    "If user asks to run code, output a single fenced python block.\n\n"
                    f"Known mistakes to avoid:\n{neg_block}"
                )),
                HumanMessage(content=(
                    f"User message:\n{user_text}\n\nPlan:\n{plan}\n\n"
                    f"Preferences:\n{pref_block}\n\nRetrieved knowledge:\n{rag_block}\n\n"
                    f"Long-term memories:\n{mem_block}"
                )),
            ])
            text = str(out.content)
            if tools["sandbox"] and "```python" in text:
                start = text.index("```python") + len("```python")
                end = text.index("```", start)
                code = text[start:end].strip()
                sandbox = get_sandbox()
                result = await sandbox.run(code)
                text = f"{text}\n\n[sandbox]\n{result}"
            elif not tools["sandbox"] and "```python" in text:
                text = f"{text}\n\n[sandbox disabled in agent tools — code not executed]"
            return {"worker_output": text, "messages": [AIMessage(content=f"[worker]\n{text[:6000]}")]}

    return worker


def make_synthesizer(ctx: GraphContext):
    from flow.infrastructure.observability.tracing import get_tracer
    tracer = get_tracer()

    async def synthesizer(state: FlowGraphState) -> dict:
        with tracer.start_as_current_span("graph.synthesizer") as span:
            span.set_attribute("execution.workspace_id", str(ctx.workspace_id))
            plan = state.get("plan") or ""
            notes = state.get("worker_output") or ""
            llm = _get_llm(ctx)
            if llm is None:
                answer = (
                    "Flow is running without OPENAI_API_KEY. "
                    f"Configure the key to enable full LLM. Plan (stub): {plan[:500]}"
                )
                return {"answer": answer, "confidence": 0.5, "messages": [AIMessage(content=answer)]}
            out = await llm.ainvoke([
                SystemMessage(content=(
                    "You are the synthesizer. Write the final concise answer. "
                    "Then on a new line write exactly: CONFIDENCE: <float 0.0-1.0> "
                    "where the float reflects how confident you are in the answer completeness."
                )),
                HumanMessage(content=f"Plan:\n{plan}\n\nWorker notes:\n{notes}"),
            ])
            raw = str(out.content)
            confidence = 0.8
            answer = raw
            if "CONFIDENCE:" in raw:
                parts = raw.rsplit("CONFIDENCE:", 1)
                answer = parts[0].strip()
                try:
                    confidence = max(0.0, min(1.0, float(parts[1].strip().split()[0])))
                except (ValueError, IndexError):
                    pass
            return {"answer": answer, "confidence": confidence, "messages": [AIMessage(content=answer)]}

    return synthesizer


# ---------------------------------------------------------------------------
# researcher-critic-writer nodes
# ---------------------------------------------------------------------------

def make_researcher(ctx: GraphContext):
    from flow.infrastructure.observability.tracing import get_tracer
    tracer = get_tracer()
    tools = _resolved_tools(ctx.agent_config)

    async def researcher(state: FlowGraphState) -> dict:
        with tracer.start_as_current_span("graph.researcher") as span:
            span.set_attribute("execution.workspace_id", str(ctx.workspace_id))
            user_text = _last_human_text(state)
            prior = state.get("research_notes") or ""
            critique = state.get("critique") or ""
            iterations = state.get("research_iterations", 0)
            rag_bits, mem_bits = await _rag_and_memory(ctx, user_text, tools)

            rag_block = "\n---\n".join(rag_bits) or "(no knowledge hits)"
            mem_block = "\n---\n".join(mem_bits) or "(no memory hits)"

            system = (
                "You are a researcher. Gather facts to answer the user's question. "
                "Be thorough. Cite sources when available."
            )
            context_parts = [f"User question:\n{user_text}"]
            if prior:
                context_parts.append(f"Prior research notes:\n{prior}")
            if critique:
                context_parts.append(f"Critic feedback to address:\n{critique}")
            context_parts.append(f"Knowledge:\n{rag_block}\nMemories:\n{mem_block}")

            llm = _get_llm(ctx)
            if llm is None:
                notes = f"Offline research: {user_text}\nKnowledge: {rag_block}"
            else:
                out = await llm.ainvoke([
                    SystemMessage(content=system),
                    HumanMessage(content="\n\n".join(context_parts)),
                ])
                notes = str(out.content)

            return {
                "research_notes": notes,
                "research_iterations": iterations + 1,
                "messages": [AIMessage(content=f"[researcher/{iterations + 1}]\n{notes[:4000]}")],
            }

    return researcher


def make_critic(ctx: GraphContext):
    from flow.infrastructure.observability.tracing import get_tracer
    tracer = get_tracer()

    async def critic(state: FlowGraphState) -> dict:
        with tracer.start_as_current_span("graph.critic") as span:
            span.set_attribute("execution.workspace_id", str(ctx.workspace_id))
            user_text = _last_human_text(state)
            notes = state.get("research_notes") or ""
            iterations = state.get("research_iterations", 0)

            llm = _get_llm(ctx)
            if llm is None or iterations >= 2:
                return {
                    "critique": "",
                    "needs_more_research": False,
                    "messages": [AIMessage(content="[critic] Research looks sufficient.")],
                }

            out = await llm.ainvoke([
                SystemMessage(content=(
                    "You are a critic. Review the research notes for completeness and accuracy. "
                    "If the research is sufficient to answer the question, respond with exactly: SUFFICIENT. "
                    "Otherwise, respond with: NEEDS_MORE: <specific gap to address>"
                )),
                HumanMessage(content=f"Question:\n{user_text}\n\nResearch notes:\n{notes}"),
            ])
            verdict = str(out.content).strip()
            needs_more = verdict.startswith("NEEDS_MORE") and iterations < 2
            critique = verdict.removeprefix("NEEDS_MORE:").strip() if needs_more else ""
            return {
                "critique": critique,
                "needs_more_research": needs_more,
                "messages": [AIMessage(content=f"[critic] {verdict[:500]}")],
            }

    return critic


def make_writer(ctx: GraphContext):
    from flow.infrastructure.observability.tracing import get_tracer
    tracer = get_tracer()

    async def writer(state: FlowGraphState) -> dict:
        with tracer.start_as_current_span("graph.writer") as span:
            span.set_attribute("execution.workspace_id", str(ctx.workspace_id))
            user_text = _last_human_text(state)
            notes = state.get("research_notes") or ""
            llm = _get_llm(ctx)
            if llm is None:
                answer = f"Research summary:\n{notes[:2000]}"
            else:
                out = await llm.ainvoke([
                    SystemMessage(content="You are a writer. Compose a polished, well-structured final answer based on the research."),
                    HumanMessage(content=f"Question:\n{user_text}\n\nResearch:\n{notes}"),
                ])
                answer = str(out.content)
            return {"answer": answer, "messages": [AIMessage(content=answer)]}

    return writer


# ---------------------------------------------------------------------------
# human-in-loop nodes
# ---------------------------------------------------------------------------

def make_human_gate(ctx: GraphContext):
    async def human_gate(state: FlowGraphState) -> dict:
        approved = state.get("approved", False)
        if not approved:
            raise NodeInterrupt(
                "Waiting for human approval. "
                "Resume the execution via POST /executions/{id}/approve"
            )
        return {"requires_approval": True}

    return human_gate


# ---------------------------------------------------------------------------
# Node registry builder
# ---------------------------------------------------------------------------

def build_node_registry(ctx: GraphContext) -> dict:
    return {
        # linear-3 / deer_flow
        "planner": make_planner(ctx),
        "worker": make_worker(ctx),
        "synthesizer": make_synthesizer(ctx),
        # researcher-critic-writer
        "researcher": make_researcher(ctx),
        "critic": make_critic(ctx),
        "writer": make_writer(ctx),
        # human-in-loop
        "human_gate": make_human_gate(ctx),
    }


# ---------------------------------------------------------------------------
# Condition registry
# ---------------------------------------------------------------------------

def should_continue_research(state: FlowGraphState) -> str:
    if state.get("needs_more_research") and state.get("research_iterations", 0) < 2:
        return "researcher"
    return "writer"


def gate_approved(state: FlowGraphState) -> str:
    return "approved" if state.get("approved") else "waiting"


CONDITION_REGISTRY: dict[str, Any] = {
    "should_continue_research": should_continue_research,
    "gate_approved": gate_approved,
}
