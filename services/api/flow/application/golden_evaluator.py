"""LLM-judge evaluator for golden set items.

Uses gpt-4o-mini to score actual vs expected output on a 0.0–1.0 scale.

Evaluation flow:
  1. For each golden item, invoke the agent's own LLM with its system prompt.
  2. Score the real output against the expected answer.
  3. INSERT a new golden_results row (never UPDATE) so history accumulates.
  4. Trigger regression/genome snapshot logic on the aggregate.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any
from uuid import UUID, uuid4

from openai import AsyncOpenAI
from flow.application.curator import check_regression_and_propose
from flow.application.genome_service import (
    _create_genome_proposal,
    _maybe_snapshot_eval_pass,
    get_active_genome,
    get_previous_active_genome,
)

logger = logging.getLogger(__name__)

_JUDGE_SYSTEM = """\
You are a strict but fair evaluator comparing an AI-generated answer to an expected answer.
Score the actual output on a 0.0–1.0 scale based on:
- Factual accuracy (most important)
- Completeness relative to expected
- Following any scoring criteria provided

Return ONLY valid JSON in this exact format, no preamble:
{"score": <float 0.0-1.0>, "rationale": "<one sentence explanation>"}
"""


async def judge_single(
    input_text: str,
    expected_output: str,
    actual_output: str,
    scoring_criteria: str | None = None,
    *,
    client: AsyncOpenAI | None = None,
) -> dict[str, Any]:
    """Score one golden item. Returns {"score": float, "rationale": str}."""
    if client is None:
        client = AsyncOpenAI()

    criteria_block = f"\nScoring criteria: {scoring_criteria}" if scoring_criteria else ""
    user_content = f"""\
Question: {input_text}

Expected answer:
{expected_output}

Actual answer:
{actual_output}{criteria_block}
"""

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _JUDGE_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            max_tokens=200,
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        return {
            "score": float(data.get("score", 0.0)),
            "rationale": str(data.get("rationale", "")),
        }
    except Exception as exc:
        logger.warning("judge_single failed: %s", exc)
        return {"score": 0.0, "rationale": f"Evaluation error: {exc}"}


async def run_agent_on_item(
    input_text: str,
    system_prompt: str,
    llm_config: dict[str, Any],
    *,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
) -> str:
    """Invoke the agent's own LLM on a single golden item input.

    Runs the LLM directly (no tools/graph) for fast, reproducible evals.
    Returns the model text response.
    """
    from flow.infrastructure.llm.providers import get_chat_model
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_chat_model(
        llm_config,
        fallback_api_keys={
            "openai": openai_api_key or os.environ.get("FLOW_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            "anthropic": anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY"),
        },
    )
    if llm is None:
        return "[no LLM configured — set FLOW_OPENAI_API_KEY or ANTHROPIC_API_KEY]"

    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=input_text))

    try:
        result = await llm.ainvoke(messages)
        return str(result.content)
    except Exception as exc:
        logger.warning("run_agent_on_item failed: %s", exc)
        return f"[LLM error: {exc}]"


async def evaluate_golden_set(
    pool: Any,
    golden_set_id: UUID,
    agent_id: UUID,
    agent_version_label: str | None,
    workspace_id: UUID | None = None,
    user_id: UUID | None = None,
    *,
    client: AsyncOpenAI | None = None,
    eval_run_id: UUID | None = None,
    system_prompt: str = "",
    llm_config: dict[str, Any] | None = None,
    openai_api_key: str | None = None,
) -> dict[str, Any]:
    """Run all items in a golden set through the agent LLM, score, and store.

    Always INSERTs new golden_results rows — never overwrites history.
    Each call creates a fresh eval_run_id so runs are distinguishable.

    Returns aggregate stats + per-item results.
    """
    if client is None:
        client = AsyncOpenAI(api_key=openai_api_key or os.environ.get("FLOW_OPENAI_API_KEY"))

    run_id = eval_run_id or uuid4()
    effective_llm_config = llm_config or {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.3}

    items = await pool.fetch(
        """
        SELECT gi.id, gi.input_text, gi.expected_output, gi.scoring_criteria
        FROM golden_items gi
        WHERE gi.set_id = $1
        ORDER BY gi.created_at
        """,
        golden_set_id,
    )

    results = []
    scores = []

    for item in items:
        actual_output = await run_agent_on_item(
            input_text=item["input_text"],
            system_prompt=system_prompt,
            llm_config=effective_llm_config,
            openai_api_key=openai_api_key,
        )

        judgment = await judge_single(
            item["input_text"],
            item["expected_output"],
            actual_output,
            item["scoring_criteria"],
            client=client,
        )

        # Always INSERT — history accumulates across runs
        await pool.execute(
            """
            INSERT INTO golden_results
                (item_id, agent_id, agent_version_label, actual_output,
                 score, grading_rationale, eval_run_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            item["id"],
            agent_id,
            agent_version_label,
            actual_output,
            judgment["score"],
            judgment["rationale"],
            run_id,
        )

        scores.append(judgment["score"])
        results.append({
            "item_id": str(item["id"]),
            "input_text": item["input_text"],
            "expected_output": item["expected_output"],
            "actual_output": actual_output,
            "score": judgment["score"],
            "rationale": judgment["rationale"],
        })

    total = len(results)
    scored = len(scores)
    avg_score = sum(scores) / scored if scored else 0.0
    pass_rate = len([s for s in scores if s >= 0.7]) / scored if scored else 0.0

    candidate_version_id = None
    if workspace_id and user_id:
        await check_regression_and_propose(
            pool=pool,
            golden_set_id=golden_set_id,
            agent_id=agent_id,
            new_avg_score=avg_score,
            results=results,
            workspace_id=workspace_id,
            user_id=user_id,
            openai_api_key=openai_api_key,
        )

        if pass_rate >= 0.7:
            try:
                candidate_version_id = await _maybe_snapshot_eval_pass(
                    pool=pool,
                    agent_id=agent_id,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    avg_score=avg_score,
                    pass_rate=pass_rate,
                )
            except Exception:
                logger.warning("genome.eval_snapshot_failed", exc_info=True)

    return {
        "eval_run_id": str(run_id),
        "total_items": total,
        "scored_items": scored,
        "avg_score": round(avg_score, 3),
        "pass_rate": round(pass_rate, 3),
        "results": results,
        "candidate_version_id": str(candidate_version_id) if candidate_version_id else None,
    }


async def auto_eval_tick(ctx: dict) -> None:
    """Cron job: nightly golden set evaluation across all workspaces."""
    pool = ctx["pool"]
    workspaces = await pool.fetch("SELECT id FROM workspaces")
    openai_key = os.environ.get("FLOW_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    client = AsyncOpenAI(api_key=openai_key)

    for ws in workspaces:
        ws_id = ws["id"]
        agent = await pool.fetchrow(
            "SELECT id FROM agents WHERE workspace_id = $1 LIMIT 1", ws_id
        )
        if not agent:
            continue

        gset = await pool.fetchrow(
            "SELECT id FROM golden_sets WHERE workspace_id = $1 LIMIT 1", ws_id
        )
        if not gset:
            continue

        logger.info("cron.auto_eval_tick.running workspace_id=%s agent_id=%s", ws_id, agent["id"])
        user = await pool.fetchrow(
            "SELECT user_id FROM workspace_members WHERE workspace_id = $1 LIMIT 1", ws_id
        )
        user_id = user["user_id"] if user else None

        active_genome = await get_active_genome(pool, agent["id"])
        version_label = active_genome.version_label if active_genome else "v1.0"
        system_prompt = active_genome.system_prompt if active_genome else ""
        llm_config: dict[str, Any] = {}
        if active_genome:
            llm_config = {
                "provider": active_genome.llm_config.provider,
                "model": active_genome.llm_config.model,
                "temperature": active_genome.llm_config.temperature,
            }

        try:
            result = await evaluate_golden_set(
                pool=pool,
                golden_set_id=gset["id"],
                agent_id=agent["id"],
                agent_version_label=version_label,
                workspace_id=ws_id,
                user_id=user_id,
                client=client,
                system_prompt=system_prompt,
                llm_config=llm_config or {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.3},
                openai_api_key=openai_key,
            )
            candidate_id_str = result.get("candidate_version_id")
            if candidate_id_str and user_id:
                from uuid import UUID as _UUID
                from flow.application.ab_runner import ABTestRunner
                candidate_id = _UUID(candidate_id_str)
                prev_genome = await get_previous_active_genome(pool, agent["id"])
                if prev_genome and prev_genome.id:
                    test_id = uuid4()
                    await pool.execute(
                        "INSERT INTO ab_tests "
                        "(id, workspace_id, golden_set_id, agent_a_id, agent_b_id, status) "
                        "VALUES ($1, $2, $3, $4, $4, 'running')",
                        test_id, ws_id, gset["id"], agent["id"],  # agent_a_id = agent_b_id: same agent, versions set on completion
                    )
                    summary = await ABTestRunner(pool, client).run(
                        test_id=test_id,
                        golden_set_id=gset["id"],
                        version_a_id=prev_genome.id,
                        version_b_id=candidate_id,
                        agent_id=agent["id"],
                    )
                    if summary.significant and summary.winner_version_id == candidate_id:
                        await _create_genome_proposal(
                            pool=pool,
                            workspace_id=ws_id,
                            user_id=user_id,
                            candidate_version_id=candidate_id,
                            title=f"Eval improvement: +{summary.delta:.3f} avg score",
                            body=(
                                f"Candidate {summary.version_b.version_label} scored "
                                f"{summary.version_b.avg_score:.3f} vs previous "
                                f"{summary.version_a.avg_score:.3f} "
                                f"(A/B test {test_id}, delta={summary.delta:.3f}). "
                                "Approve to promote."
                            ),
                        )
                else:
                    # No active baseline — promote candidate directly via proposal
                    avg_score = result.get("avg_score", 0.0)
                    await _create_genome_proposal(
                        pool=pool,
                        workspace_id=ws_id,
                        user_id=user_id,
                        candidate_version_id=candidate_id,
                        title=f"First eval improvement: {avg_score:.3f} avg score",
                        body=(
                            f"No prior active genome to compare against. "
                            f"Candidate created from prompt rewrite (confidence: "
                            f"{result.get('rewrite', {}).get('confidence', 0.0):.2f}). "
                            "Approve to make this the active version."
                        ),
                    )
        except Exception as exc:
            logger.error("cron.auto_eval_tick.failed exc=%s workspace_id=%s", exc, ws_id)
