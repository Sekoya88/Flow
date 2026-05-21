"""Node implementations for all graph templates.

Each node is a factory that captures GraphContext and returns an async callable
matching LangGraph's `(state) -> dict` signature.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import TYPE_CHECKING, Any

from flow.infrastructure.observability.logging import get_logger as _get_node_logger

_node_logger = _get_node_logger("flow.graph.node")

try:
    from langsmith import traceable as _traceable
except ImportError:

    def _traceable(**_kw):  # type: ignore[misc]
        def _wrap(fn):
            return fn

        return _wrap


from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.errors import NodeInterrupt

from flow.infrastructure.graph.state import FlowGraphState
from flow.infrastructure.llm import embeddings as emb_svc
from flow.infrastructure.persistence.repo import FlowRepository
from flow.infrastructure.tools.sandbox.factory import get_sandbox

if TYPE_CHECKING:
    from flow.infrastructure.graph.deer_graph import GraphContext


def _emit_tool_call(
    ctx: GraphContext,
    tool: str,
    input_data: dict,
    output: Any,
    duration_ms: int,
    status: str = "success",
) -> None:
    """Publish a tool_call SSE event and write a KG node. No-op when stream_hub is unavailable."""
    if ctx.stream_hub is None or ctx.execution_id is None:
        return
    ctx.stream_hub.publish(
        ctx.execution_id,
        {
            "kind": "tool_call",
            "tool": tool,
            "input": input_data,
            "output": str(output)[:2000],
            "duration_ms": duration_ms,
            "status": status,
        },
    )

    # Write tool_call node to KG (fire-and-forget)
    import asyncio

    try:
        repo = FlowRepository(ctx.pool)
        asyncio.ensure_future(
            repo.insert_tool_call_node(
                workspace_id=ctx.workspace_id,
                execution_id=ctx.execution_id,
                tool_name=tool,
                input_preview=str(input_data)[:200],
                output_preview=str(output)[:200],
                duration_ms=duration_ms,
            )
        )
    except Exception:
        pass


DEFAULT_TOOLS = {
    "retrieve": True,
    "sandbox": True,
    "long_term_memory": True,
    "tavily_search": False,
    "fetch_webpage": False,
    "arxiv_search": False,
    "hf_papers": False,
}


def _resolved_tools(cfg: dict[str, Any]) -> dict[str, bool]:
    raw = cfg.get("tools") if isinstance(cfg.get("tools"), dict) else {}
    out = {**DEFAULT_TOOLS}
    for k in DEFAULT_TOOLS:
        if k in raw:
            out[k] = bool(raw[k])
    return out


def _get_llm(ctx: GraphContext):
    from flow.infrastructure.llm.providers import get_chat_model

    cfg = ctx.agent_config or {}
    model_config = cfg.get("llm_config") or cfg.get("model") or {}
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
    rag_sources: list[dict] = []
    mem_bits: list[str] = []
    settings = ctx.settings
    use_agentic = bool(
        tools["retrieve"] and ctx.openai_api_key and settings and settings.agentic_rag_enabled and settings.qdrant_url and settings.qdrant_url.strip()
    )
    if ctx.openai_api_key and (tools["retrieve"] or tools["long_term_memory"]):
        try:
            q_emb = (await emb_svc.embed_texts(api_key=ctx.openai_api_key, texts=[user_text]))[0]
            if tools["retrieve"]:
                t0 = time.time()
                try:
                    if use_agentic:
                        from flow.infrastructure.agentic_rag.pipeline import run_agentic_retrieval

                        rag_bits = (await run_agentic_retrieval(ctx, user_text))[0]
                    else:
                        rows = await repo.search_knowledge(ctx.workspace_id, q_emb, limit=8)
                        rag_bits = [r["content"] for r in rows]
                        rag_sources = [
                            {
                                "source_id": str(r["source_id"]),
                                "title": r["source_title"],
                                "chunk_index": r["chunk_index"],
                                "preview": r["content"][:200],
                            }
                            for r in rows
                        ]
                    _emit_tool_call(ctx, "knowledge_search", {"query": user_text}, f"{len(rag_bits)} chunks", int((time.time() - t0) * 1000))
                except Exception:
                    rows = await repo.search_knowledge(ctx.workspace_id, q_emb, limit=8)
                    rag_bits = [r["content"] for r in rows]
                    rag_sources = [
                        {
                            "source_id": str(r["source_id"]),
                            "title": r["source_title"],
                            "chunk_index": r["chunk_index"],
                            "preview": r["content"][:200],
                        }
                        for r in rows
                    ]
                    _emit_tool_call(
                        ctx, "knowledge_search", {"query": user_text}, f"{len(rag_bits)} chunks (fallback)", int((time.time() - t0) * 1000)
                    )
            if tools["long_term_memory"]:
                t0 = time.time()
                try:
                    mrows = await repo.search_memories(ctx.workspace_id, ctx.agent_id, ctx.user_id, q_emb, limit=4)
                    mem_bits = [r["content"] for r in mrows]
                    _emit_tool_call(ctx, "long_term_memory", {"query": user_text}, f"{len(mem_bits)} memories", int((time.time() - t0) * 1000))
                except Exception:
                    pass
        except Exception:
            pass
    return rag_bits, rag_sources, mem_bits


# ---------------------------------------------------------------------------
# linear-3 / deer_flow nodes
# ---------------------------------------------------------------------------


def make_planner(ctx: GraphContext):
    from flow.infrastructure.observability.tracing import get_tracer
    from flow.infrastructure.persistence.repo import FlowRepository

    tracer = get_tracer()
    repo = FlowRepository(ctx.pool)

    @_traceable(name="flow.planner", run_type="chain")
    async def planner(state: FlowGraphState) -> dict:
        _t0 = time.monotonic()
        with tracer.start_as_current_span("graph.planner") as span:
            span.set_attribute("execution.workspace_id", str(ctx.workspace_id))
            user_text = _last_human_text(state)
            llm = _get_llm(ctx)

            # Query ReasoningBank for similar past patterns
            pattern_block = ""
            if ctx.openai_api_key:
                try:
                    from flow.infrastructure.llm import embeddings as emb_svc

                    q_emb = (await emb_svc.embed_texts(api_key=ctx.openai_api_key, texts=[user_text]))[0]
                    patterns = await repo.search_reasoning_patterns(ctx.workspace_id, ctx.agent_id, q_emb, limit=3)
                    if patterns:
                        lines = []
                        for p in patterns:
                            lines.append(f"[Pattern score={p['score']:.2f}]\nProblem: {p['problem_summary']}\nSolution: {p['solution_steps']}")
                            await repo.increment_pattern_use(p["id"])
                        pattern_block = "\n\n".join(lines)
                except Exception:
                    pass  # reasoning bank query is best-effort

            # Load active agent skills via centralized SkillLoader (Phase 1)
            skills_block = ""
            matched_skill_dicts: list[dict] = []
            try:
                from flow.application.skill_loader import SkillLoader

                loader = SkillLoader(repo)
                matched = await loader.load_and_match(
                    agent_id=ctx.agent_id,
                    workspace_id=ctx.workspace_id,
                    query=user_text,
                    execution_id=ctx.execution_id,
                )
                if matched:
                    skills_block = loader.format_xml(matched)
                    matched_skill_dicts = loader.to_state_dicts(matched)
                    if ctx.stream_hub:
                        ctx.stream_hub.publish_agent_event(ctx.agent_id, {
                            "type": "skills_matched",
                            "skills": [{"name": s.name, "version": s.version} for s in matched]
                        })
            except Exception:
                pass

            # JEPA: read prediction from previous metacognition
            prediction_hint = ""
            try:
                last_pred = await repo.get_latest_prediction(ctx.workspace_id, ctx.agent_id)
                if last_pred:
                    prediction_hint = f"\n\n[METACOGNITION] Previous run predicted this topic: {last_pred}"
            except Exception:
                pass

            # Read cross-thread facts from AsyncPostgresStore
            store_facts_block = ""
            if ctx.store is not None:
                try:
                    namespace = (str(ctx.workspace_id), str(ctx.agent_id), "facts")
                    store_results = await ctx.store.asearch(namespace, query=user_text, limit=5)
                    if store_results:
                        lines = [r.value.get("content", "") for r in store_results if r.value.get("content")]
                        if lines:
                            store_facts_block = "Remembered facts:\n" + "\n".join(f"- {fact}" for fact in lines)
                except Exception:
                    pass  # store read is best-effort

            if llm is None:
                plan = "Offline plan: clarify goal, gather facts, draft answer."
                if pattern_block:
                    plan = f"[Reasoning patterns found]\n{pattern_block}\n\n{plan}"
            else:
                system = "You are a planning node. Output a short numbered plan (max 5 bullets)."
                if store_facts_block:
                    system += f"\n\n{store_facts_block}"
                if pattern_block:
                    system = (
                        "You are a planning node. Output a short numbered plan (max 5 bullets).\n\n"
                        "PAST SUCCESSFUL PATTERNS (use as inspiration, don't copy verbatim):\n" + pattern_block
                    )
                if skills_block:
                    system += f"\n\n{skills_block}"
                if prediction_hint:
                    system += prediction_hint
                out = await llm.ainvoke(
                    [
                        SystemMessage(content=system),
                        HumanMessage(content=user_text),
                    ]
                )
                plan = str(out.content)
            _node_logger.info("node.done", node="planner", duration_ms=int((time.monotonic() - _t0) * 1000))

            # Emit parsed plan as todo_update to agent observability channel
            if ctx.stream_hub and plan and ctx.agent_id:
                todo_lines = [
                    re.sub(r"^(\d+[\.\)]\s*|\*\s*|-\s*)", "", l).strip()
                    for l in plan.split("\n")
                    if l.strip()
                ]
                todos = [{"status": "pending", "content": t} for t in todo_lines if t]
                if todos:
                    ctx.stream_hub.publish_agent_event(ctx.agent_id, {
                        "type": "todo_update",
                        "todos": todos,
                    })

            result: dict = {"plan": plan, "messages": [AIMessage(content=f"[planner]\n{plan}")]}
            if matched_skill_dicts:
                result["active_skills"] = matched_skill_dicts
            return result

    return planner


def make_worker(ctx: GraphContext):
    from flow.infrastructure.observability.tracing import get_tracer

    tracer = get_tracer()
    tools = _resolved_tools(ctx.agent_config)
    repo = FlowRepository(ctx.pool)

    @_traceable(name="flow.worker", run_type="chain")
    async def worker(state: FlowGraphState) -> dict:
        _t0 = time.monotonic()
        with tracer.start_as_current_span("graph.worker") as span:
            span.set_attribute("execution.workspace_id", str(ctx.workspace_id))
            plan = state.get("plan") or ""
            user_text = _last_human_text(state)
            rag_bits, rag_sources, mem_bits = await _rag_and_memory(ctx, user_text, tools)
            try:
                prefs = await repo.load_profile(ctx.workspace_id, ctx.user_id, ctx.agent_id)
            except Exception:
                prefs = []
            pref_lines = [f"{r['class']}: {r['value']}" for r in prefs[:20]]

            neg_rows = await repo.list_agent_negatives(ctx.workspace_id, ctx.agent_id, limit=5)
            neg_bits = [r["content"] for r in neg_rows]

            numbered_snippets = "\n\n".join(f"[{i + 1}] {chunk}" for i, chunk in enumerate(rag_bits)) or "(knowledge RAG disabled or no hits)"
            mem_block = "\n---\n".join(mem_bits) or "(long-term memory off or no hits)"
            pref_block = "\n".join(pref_lines) or "(no user preferences)"
            neg_block = "\n".join(f"- {n}" for n in neg_bits) or "(none)"

            llm = _get_llm(ctx)
            if llm is None:
                body = f"RAG:\n{numbered_snippets}\n\nMemories:\n{mem_block}\n\nUser prefs:\n{pref_block}\n\nPlan:\n{plan}"
                _node_logger.info("node.done", node="worker", duration_ms=int((time.monotonic() - _t0) * 1000))
                return {
                    "worker_output": body[:8000],
                    "rag_sources": rag_sources,
                    "messages": [AIMessage(content=f"[worker]\n{body[:4000]}")],
                }

            out = await llm.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "You are a worker node. Use the plan, user message, retrieved snippets, "
                            "long-term memories, and preferences. Produce structured research notes. "
                            "Reference knowledge snippets by their [N] number when relevant. "
                            "If user asks to run code, output a single fenced python block.\n\n"
                            f"Known mistakes to avoid:\n{neg_block}"
                        )
                    ),
                    HumanMessage(
                        content=(
                            f"User message:\n{user_text}\n\nPlan:\n{plan}\n\n"
                            f"Preferences:\n{pref_block}\n\nRetrieved knowledge (cite as [N]):\n{numbered_snippets}\n\n"
                            f"Long-term memories:\n{mem_block}"
                        )
                    ),
                ]
            )
            text = str(out.content)
            if tools["sandbox"] and "```python" in text:
                start = text.index("```python") + len("```python")
                end = text.index("```", start)
                code = text[start:end].strip()
                t0 = time.time()
                sandbox = get_sandbox()
                result = await sandbox.run(code)
                _emit_tool_call(ctx, "sandbox", {"code": code[:300]}, result[:1000], int((time.time() - t0) * 1000))
                text = f"{text}\n\n[sandbox]\n{result}"
            elif not tools["sandbox"] and "```python" in text:
                text = f"{text}\n\n[sandbox disabled in agent tools — code not executed]"
            _node_logger.info("node.done", node="worker", duration_ms=int((time.monotonic() - _t0) * 1000))
            return {
                "worker_output": text,
                "rag_sources": rag_sources,
                "messages": [AIMessage(content=f"[worker]\n{text[:6000]}")],
            }

    return worker


def make_synthesizer(ctx: GraphContext):
    from flow.infrastructure.observability.tracing import get_tracer

    tracer = get_tracer()

    @_traceable(name="flow.synthesizer", run_type="chain")
    async def synthesizer(state: FlowGraphState) -> dict:
        _t0 = time.monotonic()
        with tracer.start_as_current_span("graph.synthesizer") as span:
            span.set_attribute("execution.workspace_id", str(ctx.workspace_id))
            plan = state.get("plan") or ""
            notes = state.get("worker_output") or ""
            rag_sources = state.get("rag_sources") or []
            llm = _get_llm(ctx)
            if llm is None:
                answer = f"Flow is running without OPENAI_API_KEY. Configure the key to enable full LLM. Plan (stub): {plan[:500]}"
                _node_logger.info("node.done", node="synthesizer", duration_ms=int((time.monotonic() - _t0) * 1000))
                return {"answer": answer, "confidence": 0.5, "messages": [AIMessage(content=answer)]}

            citation_instruction = ""
            if rag_sources:
                citation_instruction = (
                    "\n\nWhen the answer draws on retrieved knowledge, add inline citation markers "
                    "like [1] or [2] where relevant. The numbers correspond to the snippets the "
                    "worker received, numbered starting from 1."
                )

            out = await llm.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "You are the synthesizer. Write the final concise answer. "
                            "Then on a new line write exactly: CONFIDENCE: <float 0.0-1.0> "
                            "where the float reflects how confident you are in the answer completeness." + citation_instruction
                        )
                    ),
                    HumanMessage(content=f"Plan:\n{plan}\n\nWorker notes:\n{notes}"),
                ]
            )
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
            # Persist answer as fact in cross-thread store (best-effort)
            if ctx.store is not None and answer:
                try:
                    import uuid as _uuid

                    namespace = (str(ctx.workspace_id), str(ctx.agent_id), "facts")
                    await ctx.store.aput(
                        namespace,
                        str(_uuid.uuid4()),
                        {"content": answer[:500], "execution_id": str(ctx.execution_id or "")},
                    )
                except Exception:
                    pass  # store write is best-effort

            _node_logger.info("node.done", node="synthesizer", duration_ms=int((time.monotonic() - _t0) * 1000))
            return {
                "answer": answer,
                "confidence": confidence,
                "messages": [AIMessage(content=answer)],
            }

    return synthesizer


def make_reflector(ctx: GraphContext):
    """MetaCognition node (Phase 2) — enhanced reflector with:
    1. JEPA-style grading + prediction (existing)
    2. Per-skill contribution scoring (NEW)
    3. Mutation proposals when grade <= 2 (NEW)
    4. Metacognitive journal entries (NEW)
    5. Confidence calibration tracking (NEW)
    6. Bandit arm updates (Phase 3a)
    """
    from flow.infrastructure.observability.tracing import get_tracer

    tracer = get_tracer()
    repo = FlowRepository(ctx.pool)

    _REFLECTION_PROMPT = """\
You are a metacognition node implementing JEPA-style self-improvement. Given the user question, plan, and answer:

1. GRADE: Rate answer quality 1-5.
2. PREDICTION: Predict the user's most likely follow-up question or topic (1 sentence). This helps the agent pre-load relevant skills and context for the next turn.
3. SKILL: If grade >= 4 and the approach was novel/reusable, suggest a skill.
4. ISSUE: If grade <= 2, note what went wrong.

Output ONLY valid JSON:
{{"grade": <int>, "prediction": "likely next question or topic", "skill_suggestion": {{"name": "kebab-case-name", "description": "When to use this skill", "triggers": ["trigger phrase 1"], "body": "## Instructions\\n..."}} | null, "issue": "..." | null}}
"""

    @_traceable(name="flow.reflector", run_type="chain")
    async def reflector(state: FlowGraphState) -> dict:
        _t0 = time.monotonic()
        with tracer.start_as_current_span("graph.reflector") as span:
            span.set_attribute("execution.workspace_id", str(ctx.workspace_id))

            answer = state.get("answer") or state.get("worker_output") or ""
            if len(str(answer)) < 100:
                _node_logger.info("node.skip", node="reflector", reason="short_answer")
                return {"reflection": {"grade": 3, "skipped": True}}

            llm = _get_llm(ctx)
            if llm is None:
                return {"reflection": {"grade": 3, "skipped": True}}

            user_text = _last_human_text(state)
            plan = state.get("plan") or ""
            confidence = state.get("confidence") or 0.8
            active_skills = state.get("active_skills") or []

            try:
                import json as _json

                out = await llm.ainvoke(
                    [
                        SystemMessage(content=_REFLECTION_PROMPT),
                        HumanMessage(content=f"Question: {user_text[:500]}\n\nPlan: {plan[:500]}\n\nAnswer: {str(answer)[:2000]}"),
                    ]
                )
                raw = str(out.content).strip()
                if "```" in raw:
                    raw = raw.split("```")[1].removeprefix("json").strip()
                data = _json.loads(raw)
                grade = int(data.get("grade", 3))

                skill_sug = data.get("skill_suggestion")
                if skill_sug and isinstance(skill_sug, dict) and grade >= 4:
                    sname = skill_sug.get("name", "").strip()
                    sdesc = skill_sug.get("description", "").strip()
                    striggers = skill_sug.get("triggers", [])
                    sbody = skill_sug.get("body", "").strip()
                    if sname and sbody:
                        from flow.application.skill_parser import ParsedSkill

                        skill = ParsedSkill(
                            name=sname,
                            description=sdesc,
                            triggers=striggers if isinstance(striggers, list) else [],
                            metadata={"author": "flow-reflector", "auto_generated": True},
                            body_md=sbody,
                        )
                        try:
                            await repo.upsert_agent_skill(
                                agent_id=ctx.agent_id,
                                workspace_id=ctx.workspace_id,
                                name=sname,
                                content_md=skill.to_frontmatter_md(),
                            )
                            _node_logger.info("reflector.skill_created", skill=sname, grade=grade)
                        except Exception:
                            pass
                        else:
                            # Snapshot genome as CANDIDATE + create proposal for human review
                            try:
                                from flow.application.genome_service import (
                                    _create_genome_proposal,
                                    snapshot_genome,
                                )
                                from flow.domain.genome import VersionStatus, VersionTrigger

                                candidate_id = await snapshot_genome(
                                    pool=ctx.pool,
                                    agent_id=ctx.agent_id,
                                    workspace_id=ctx.workspace_id,
                                    trigger=VersionTrigger.SKILL_CREATED,
                                    created_by=None,
                                    status=VersionStatus.CANDIDATE,
                                )
                                await _create_genome_proposal(
                                    pool=ctx.pool,
                                    workspace_id=ctx.workspace_id,
                                    user_id=ctx.user_id,
                                    candidate_version_id=candidate_id,
                                    title=f"New skill learned: {sname}",
                                    body=(
                                        f"Reflector grade {grade}/5. Skill '{sname}' auto-created. Approve to promote this genome version to active."
                                    ),
                                )
                            except Exception:
                                _node_logger.warning("genome.snapshot_failed_after_skill", exc_info=True)

                prediction = data.get("prediction", "")

                # Write metacog node to KG (best-effort)
                if ctx.execution_id is not None:
                    try:
                        _skill_name = skill_sug.get("name") if (skill_sug and isinstance(skill_sug, dict) and grade >= 4) else None
                        await repo.insert_metacog_node(
                            workspace_id=ctx.workspace_id,
                            execution_id=ctx.execution_id,
                            grade=grade,
                            issue=data.get("issue"),
                            skill_created=_skill_name,
                            prediction=prediction or None,
                        )
                    except Exception:
                        pass

                # Store prediction for next run (JEPA-style)
                if prediction and ctx.execution_id:
                    try:
                        await repo.store_prediction(
                            workspace_id=ctx.workspace_id,
                            agent_id=ctx.agent_id,
                            user_id=ctx.user_id,
                            prediction=prediction,
                            execution_id=ctx.execution_id,
                        )
                    except Exception:
                        pass

                # === Phase 2: MetaCognition Service integration ===
                metacog_state: dict = {}
                try:
                    from uuid import uuid4 as _uuid4

                    from flow.application.metacog_service import MetaCogEntry, MetaCogService

                    metacog = MetaCogService(ctx.pool)

                    skill_scores = await metacog.evaluate_skills(
                        execution_id=ctx.execution_id or _uuid4(),
                        matched_skills=active_skills,
                        grade=grade,
                        user_text=user_text,
                        answer=str(answer)[:2000],
                        llm=llm,
                    )

                    cal_error = await metacog.calibrate_confidence(
                        agent_id=ctx.agent_id,
                        workspace_id=ctx.workspace_id,
                        predicted_confidence=float(confidence),
                        actual_grade=grade,
                    )

                    mutations = await metacog.propose_mutations(
                        agent_id=ctx.agent_id,
                        workspace_id=ctx.workspace_id,
                        grade=grade,
                        skill_scores=skill_scores,
                        user_text=user_text,
                        answer=str(answer)[:2000],
                        llm=llm,
                    )

                    entry = MetaCogEntry(
                        execution_id=ctx.execution_id,
                        grade=grade,
                        prediction=prediction,
                        calibration_error=cal_error,
                        skill_scores=skill_scores,
                        mutations_proposed=mutations,
                        reasoning=data.get("issue") or "",
                    )
                    await metacog.update_journal(ctx.agent_id, ctx.workspace_id, entry)

                    metacog_state = {
                        "grade": grade,
                        "calibration_error": cal_error,
                        "skill_scores": [
                            {"name": s.skill_name, "contribution": s.contribution}
                            for s in skill_scores
                        ],
                        "mutations_count": len(mutations),
                    }
                    if ctx.stream_hub:
                        ctx.stream_hub.publish_agent_event(ctx.agent_id, {
                            "type": "metacog_evaluated",
                            "grade": grade,
                            "mutations_proposed": len(mutations),
                            "skill_scores": [
                                {"name": s.skill_name, "contribution": s.contribution}
                                for s in skill_scores
                            ]
                        })
                except Exception:
                    _node_logger.debug("metacog_service integration failed", exc_info=True)

                # === Phase 3a: Bandit arm updates ===
                try:
                    from uuid import UUID as _UUID

                    from flow.application.rl_bandit import SkillBandit

                    bandit = SkillBandit(ctx.pool)
                    reward = max(0.0, min(1.0, (grade - 1) / 4.0))
                    for skill_dict in active_skills:
                        sid = skill_dict.get("skill_id")
                        if sid:
                            await bandit.update(ctx.agent_id, _UUID(sid), reward)
                            if ctx.stream_hub:
                                ctx.stream_hub.publish_agent_event(ctx.agent_id, {
                                    "type": "skill_arm_updated",
                                    "skill_id": sid,
                                    "reward": reward,
                                })
                except Exception:
                    pass  # bandit updates are best-effort

                _node_logger.info("node.done", node="reflector", grade=grade, duration_ms=int((time.monotonic() - _t0) * 1000))
                result: dict = {"reflection": data, "prediction": prediction}
                if metacog_state:
                    result["metacog_state"] = metacog_state
                return result
            except Exception as exc:
                _node_logger.debug("reflector failed: %s", exc)
                return {"reflection": {"grade": 3, "error": str(exc)}}

    return reflector


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
            rag_bits, _rag_src, mem_bits = await _rag_and_memory(ctx, user_text, tools)

            rag_block = "\n---\n".join(rag_bits) or "(no knowledge hits)"
            mem_block = "\n---\n".join(mem_bits) or "(no memory hits)"

            system = "You are a researcher. Gather facts to answer the user's question. Be thorough. Cite sources when available."
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
                out = await llm.ainvoke(
                    [
                        SystemMessage(content=system),
                        HumanMessage(content="\n\n".join(context_parts)),
                    ]
                )
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

            out = await llm.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "You are a critic. Review the research notes for completeness and accuracy. "
                            "If the research is sufficient to answer the question, respond with exactly: SUFFICIENT. "
                            "Otherwise, respond with: NEEDS_MORE: <specific gap to address>"
                        )
                    ),
                    HumanMessage(content=f"Question:\n{user_text}\n\nResearch notes:\n{notes}"),
                ]
            )
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
                out = await llm.ainvoke(
                    [
                        SystemMessage(content="You are a writer. Compose a polished, well-structured final answer based on the research."),
                        HumanMessage(content=f"Question:\n{user_text}\n\nResearch:\n{notes}"),
                    ]
                )
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
            raise NodeInterrupt("Waiting for human approval. Resume the execution via POST /executions/{id}/approve")
        return {"requires_approval": True}

    return human_gate


# ---------------------------------------------------------------------------
# Tool-agent: LangChain function-calling node with web + workspace tools
# ---------------------------------------------------------------------------


def _check_tool_prereqs(tool_name: str, ctx: GraphContext) -> str | None:
    """Return an error string if tool requirements are not met, else None."""
    settings = ctx.settings
    PREREQS: dict[str, tuple[str, str]] = {
        "tavily_search": ("tavily_api_key", "FLOW_TAVILY_API_KEY not configured — set it in settings"),
        "knowledge_search": ("openai_api_key", "OpenAI API key required for knowledge search embedding"),
        "long_term_memory": ("openai_api_key", "OpenAI API key required for memory search embedding"),
    }
    if tool_name not in PREREQS:
        return None
    attr, msg = PREREQS[tool_name]
    if not (settings and getattr(settings, attr, None)):
        return msg
    return None


def _build_context_tools(ctx: GraphContext) -> list:
    """Return LangChain StructuredTool list enabled in agent config."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    enabled: dict = ctx.agent_config.get("tools") or {}
    settings = ctx.settings
    lc_tools: list = []

    async def _emit_wrap(tool_name: str, coro, input_data: dict):
        # Tool monitor: check prerequisites before invoking
        prereq_err = _check_tool_prereqs(tool_name, ctx)
        if prereq_err:
            return f"[tool_monitor] {prereq_err}"
        t0 = time.time()
        try:
            result = await coro
            _emit_tool_call(ctx, tool_name, input_data, result, int((time.time() - t0) * 1000))
            return result
        except Exception as exc:
            _emit_tool_call(ctx, tool_name, input_data, str(exc), int((time.time() - t0) * 1000), "error")
            raise

    if enabled.get("tavily_search"):
        from flow.infrastructure.tools.web import run_tavily_search

        class TavilyArgs(BaseModel):
            query: str = Field(description="Search query")
            max_results: int = Field(default=5, description="Number of results")

        async def _tavily(query: str, max_results: int = 5) -> str:
            r = await _emit_wrap(
                "tavily_search",
                run_tavily_search(query, max_results, (settings.tavily_api_key or "") if settings else ""),
                {"query": query, "max_results": max_results},
            )
            return str(r)

        lc_tools.append(
            StructuredTool.from_function(
                coroutine=_tavily,
                name="tavily_search",
                description="Search the web using Tavily. Use for current events, news, and factual queries.",
                args_schema=TavilyArgs,
            )
        )

    if enabled.get("fetch_webpage"):
        from flow.infrastructure.tools.web import run_fetch_webpage

        class FetchArgs(BaseModel):
            url: str = Field(description="URL to fetch and read")

        async def _fetch(url: str) -> str:
            r = await _emit_wrap("fetch_webpage", run_fetch_webpage(url), {"url": url})
            return str(r)

        lc_tools.append(
            StructuredTool.from_function(
                coroutine=_fetch, name="fetch_webpage", description="Fetch and extract readable text from any URL.", args_schema=FetchArgs
            )
        )

    if enabled.get("arxiv_search"):
        from flow.infrastructure.tools.web import run_arxiv_search

        class ArxivArgs(BaseModel):
            query: str = Field(description="ArXiv search query (topic, keywords, or author)")
            max_results: int = Field(default=5)

        async def _arxiv(query: str, max_results: int = 5) -> str:
            r = await _emit_wrap("arxiv_search", run_arxiv_search(query, max_results), {"query": query, "max_results": max_results})
            return str(r)

        lc_tools.append(
            StructuredTool.from_function(
                coroutine=_arxiv,
                name="arxiv_search",
                description="Search ArXiv for academic papers. Returns title, abstract, URL, publish date.",
                args_schema=ArxivArgs,
            )
        )

    if enabled.get("hf_papers"):
        from flow.infrastructure.tools.web import run_hf_papers

        class HFPapersArgs(BaseModel):
            date: str = Field(default="", description="Date as YYYY-MM-DD. Empty = today.")

        async def _hf(date: str = "") -> str:
            r = await _emit_wrap("hf_papers", run_hf_papers(date), {"date": date or "today"})
            return str(r)

        lc_tools.append(
            StructuredTool.from_function(
                coroutine=_hf,
                name="hf_papers",
                description="Get HuggingFace Daily Papers with upvotes. Best for trending AI/ML research.",
                args_schema=HFPapersArgs,
            )
        )

    if enabled.get("sandbox"):

        class SandboxArgs(BaseModel):
            code: str = Field(description="Python code to execute")

        async def _sandbox(code: str) -> str:
            t0 = time.time()
            sandbox = get_sandbox()
            result = await sandbox.run(code)
            _emit_tool_call(ctx, "sandbox", {"code": code[:300]}, result[:1000], int((time.time() - t0) * 1000))
            return result

        lc_tools.append(
            StructuredTool.from_function(
                coroutine=_sandbox, name="sandbox", description="Execute Python code and return stdout/stderr.", args_schema=SandboxArgs
            )
        )

    if enabled.get("retrieve"):
        repo = FlowRepository(ctx.pool)

        class KnowledgeArgs(BaseModel):
            query: str = Field(description="Semantic search query over workspace documents")

        async def _knowledge(query: str) -> str:
            if not ctx.openai_api_key:
                return "(knowledge search requires OpenAI API key)"
            t0 = time.time()
            q_emb = (await emb_svc.embed_texts(api_key=ctx.openai_api_key, texts=[query]))[0]
            rows = await repo.search_knowledge(ctx.workspace_id, q_emb, limit=6)
            chunks = [r["content"] for r in rows]
            _emit_tool_call(ctx, "knowledge_search", {"query": query}, f"{len(chunks)} chunks", int((time.time() - t0) * 1000))
            return "\n\n---\n\n".join(chunks) or "(no results)"

        lc_tools.append(
            StructuredTool.from_function(
                coroutine=_knowledge,
                name="knowledge_search",
                description="Search workspace knowledge base (uploaded PDFs, docs, URLs).",
                args_schema=KnowledgeArgs,
            )
        )

    # subagent_call — inline sub-graph execution
    class SubagentArgs(BaseModel):
        agent_name: str = Field(description="Name of the target agent in this workspace")
        message: str = Field(description="Message to send to the subagent")

    async def _subagent_call(agent_name: str, message: str) -> str:
        t0 = time.time()
        call_id = str(uuid.uuid4())
        # Emit start event so the parent run UI can render the inline card immediately
        hub = getattr(ctx, "stream_hub", None)
        parent_exec_id = getattr(ctx, "execution_id", None)
        if hub is not None and parent_exec_id is not None:
            try:
                hub.publish(
                    parent_exec_id,
                    {
                        "kind": "subagent_start",
                        "agent_name": agent_name,
                        "message": message[:500],
                    },
                )
            except Exception:
                pass
        if hub is not None and ctx.agent_id is not None:
            hub.publish_agent_event(ctx.agent_id, {
                "type": "subagent_call",
                "id": call_id,
                "status": "running",
                "description": message[:500],
                "subagent_type": agent_name,
                "result": None,
                "started_at": t0,
                "completed_at": None,
            })
        # Also persist a start row so a reload can replay it
        if parent_exec_id is not None and ctx.pool is not None:
            try:
                from flow.infrastructure.persistence.repo import FlowRepository as _RepoStart

                _rs = _RepoStart(ctx.pool)
                await _rs.insert_event(
                    parent_exec_id,
                    "subagent_start",
                    {
                        "agent_name": agent_name,
                        "message": message[:500],
                    },
                )
            except Exception:
                pass

        try:
            from flow.infrastructure.graph.deer_graph import GraphContext as _GCtx
            from flow.infrastructure.graph.deer_graph import build_deer_flow_graph
            from flow.infrastructure.persistence.repo import FlowRepository as _Repo

            _repo = _Repo(ctx.pool)
            # Find agent by name in workspace
            agents = await _repo.list_agents(ctx.workspace_id)
            target = next((a for a in agents if a["name"].lower() == agent_name.lower()), None)
            if target is None:
                err = f"[subagent_call] Agent '{agent_name}' not found in workspace."
                if hub is not None and parent_exec_id is not None:
                    hub.publish(
                        parent_exec_id,
                        {
                            "kind": "subagent_done",
                            "agent_name": agent_name,
                            "answer": err,
                            "duration_ms": int((time.time() - t0) * 1000),
                            "status": "error",
                        },
                    )
                return err
            sub_config = target["config"] if isinstance(target["config"], dict) else {}
            sub_ctx = _GCtx(
                pool=ctx.pool,
                workspace_id=ctx.workspace_id,
                agent_id=target["id"],
                user_id=ctx.user_id,
                openai_api_key=ctx.openai_api_key,
                agent_config=sub_config,
                anthropic_api_key=ctx.anthropic_api_key,
                execution_id=None,
                settings=ctx.settings,
                stream_hub=None,  # sub-runs don't stream to parent SSE
            )
            graph = build_deer_flow_graph(sub_ctx)
            from langchain_core.messages import HumanMessage as _HM

            result_state = await graph.ainvoke({"messages": [_HM(content=message)]})
            answer = result_state.get("answer") or result_state.get("worker_output") or ""
            if not answer:
                msgs = result_state.get("messages") or []
                answer = str(msgs[-1].content) if msgs else "(no answer)"
            duration_ms = int((time.time() - t0) * 1000)
            _emit_tool_call(ctx, "subagent_call", {"agent_name": agent_name, "message": message[:200]}, str(answer)[:500], duration_ms)
            # Stream done event + persist
            if hub is not None and parent_exec_id is not None:
                try:
                    hub.publish(
                        parent_exec_id,
                        {
                            "kind": "subagent_done",
                            "agent_name": agent_name,
                            "message": message[:500],
                            "answer": str(answer)[:4000],
                            "duration_ms": duration_ms,
                            "status": "success",
                        },
                    )
                except Exception:
                    pass
            if hub is not None and ctx.agent_id is not None:
                hub.publish_agent_event(ctx.agent_id, {
                    "type": "subagent_call",
                    "id": call_id,
                    "status": "complete",
                    "description": message[:500],
                    "subagent_type": agent_name,
                    "result": str(answer)[:2000],
                    "started_at": t0,
                    "completed_at": time.time(),
                })
            if parent_exec_id is not None and ctx.pool is not None:
                try:
                    from flow.infrastructure.persistence.repo import FlowRepository as _RepoDone

                    _rd = _RepoDone(ctx.pool)
                    await _rd.insert_event(
                        parent_exec_id,
                        "subagent_done",
                        {
                            "agent_name": agent_name,
                            "message": message[:500],
                            "answer": str(answer)[:4000],
                            "duration_ms": duration_ms,
                            "status": "success",
                        },
                    )
                except Exception:
                    pass
            return str(answer)[:4000]
        except Exception as exc:
            duration_ms = int((time.time() - t0) * 1000)
            _emit_tool_call(ctx, "subagent_call", {"agent_name": agent_name, "message": message[:200]}, str(exc), duration_ms, "error")
            if hub is not None and parent_exec_id is not None:
                try:
                    hub.publish(
                        parent_exec_id,
                        {
                            "kind": "subagent_done",
                            "agent_name": agent_name,
                            "answer": str(exc),
                            "duration_ms": duration_ms,
                            "status": "error",
                        },
                    )
                except Exception:
                    pass
            if hub is not None and ctx.agent_id is not None:
                hub.publish_agent_event(ctx.agent_id, {
                    "type": "subagent_call",
                    "id": call_id,
                    "status": "error",
                    "description": message[:500],
                    "subagent_type": agent_name,
                    "result": str(exc),
                    "started_at": t0,
                    "completed_at": time.time(),
                })
            return f"[subagent_call] Error: {exc}"

    lc_tools.append(
        StructuredTool.from_function(
            coroutine=_subagent_call,
            name="subagent_call",
            description="Invoke another agent in this workspace as a subagent. Returns the subagent's answer. Use when you need to delegate a subtask to a specialized agent.",
            args_schema=SubagentArgs,
        )
    )

    return lc_tools


def make_tool_agent(ctx: GraphContext):
    """ReAct-style node: LLM with bound tools, emits tool_call SSE per invocation."""
    from langchain_core.messages import ToolMessage

    from flow.infrastructure.observability.tracing import get_tracer

    tracer = get_tracer()

    @_traceable(name="flow.tool_agent", run_type="chain")
    async def tool_agent(state: FlowGraphState) -> dict:
        _t0 = time.monotonic()
        with tracer.start_as_current_span("graph.tool_agent") as span:
            span.set_attribute("execution.workspace_id", str(ctx.workspace_id))
            user_text = _last_human_text(state)
            plan = state.get("plan") or ""

            lc_tools = _build_context_tools(ctx)
            llm = _get_llm(ctx)

            if llm is None:
                _node_logger.info("node.done", node="tool_agent", duration_ms=int((time.monotonic() - _t0) * 1000))
                return {"worker_output": "No LLM configured.", "messages": [AIMessage(content="No LLM configured.")]}

            system_prompt = (ctx.agent_config or {}).get(
                "system_prompt",
                "You are a helpful research assistant. Use the available tools to answer the user's question thoroughly.",
            )
            msgs: list = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Plan:\n{plan}\n\nUser request:\n{user_text}" if plan else user_text),
            ]

            llm_with_tools = llm.bind_tools(lc_tools) if lc_tools else llm

            for _ in range(8):  # max ReAct iterations
                response = await llm_with_tools.ainvoke(msgs)
                msgs.append(response)
                tool_calls = getattr(response, "tool_calls", None) or []
                if not tool_calls:
                    break
                for tc in tool_calls:
                    tool_name = tc["name"]
                    tool_input = tc["args"]
                    tool_obj = next((t for t in lc_tools if t.name == tool_name), None)
                    try:
                        result = await tool_obj.arun(tool_input) if tool_obj else f"Tool '{tool_name}' not available"
                    except Exception as exc:
                        result = f"Error: {exc}"
                    msgs.append(ToolMessage(content=str(result)[:4000], tool_call_id=tc["id"]))

            last_content = str(getattr(msgs[-1], "content", "") or "")
            _node_logger.info("node.done", node="tool_agent", duration_ms=int((time.monotonic() - _t0) * 1000))
            return {
                "worker_output": last_content,
                "messages": [AIMessage(content=last_content[:6000])],
            }

    return tool_agent


# ---------------------------------------------------------------------------
# Node registry builder
# ---------------------------------------------------------------------------


def build_node_registry(ctx: GraphContext) -> dict:
    return {
        # linear-3 / deer_flow
        "planner": make_planner(ctx),
        "worker": make_worker(ctx),
        "synthesizer": make_synthesizer(ctx),
        "reflector": make_reflector(ctx),
        # tool-agent
        "tool_agent": make_tool_agent(ctx),
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


async def _tool_update_skill(ctx: GraphContext, repo: FlowRepository, skill_name: str, content: str) -> str:
    """Create or update an agent skill. Returns confirmation."""
    try:
        await repo.upsert_agent_skill(
            agent_id=ctx.agent_id,
            workspace_id=ctx.workspace_id,
            name=skill_name,
            content_md=content,
        )
        return f"Skill '{skill_name}' saved (new version)."
    except Exception as e:
        return f"Failed to save skill: {e}"


CONDITION_REGISTRY: dict[str, Any] = {
    "should_continue_research": should_continue_research,
    "gate_approved": gate_approved,
}
