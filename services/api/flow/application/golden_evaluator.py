"""LLM-judge evaluator for golden set items.

Uses gpt-4o-mini to score actual vs expected output on a 0.0–1.0 scale.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any
from uuid import UUID

from openai import AsyncOpenAI
from flow.application.curator import check_regression_and_propose
from flow.application.genome_service import _maybe_snapshot_eval_pass, get_active_genome

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


async def evaluate_golden_set(
    pool: Any,
    golden_set_id: UUID,
    agent_id: UUID,
    agent_version_label: str | None,
    workspace_id: UUID | None = None,
    user_id: UUID | None = None,
    *,
    client: AsyncOpenAI | None = None,
) -> dict[str, Any]:
    """Run all items in a golden set against stored execution outputs.
    
    This is called *after* executions have already been run — it judges
    the outputs stored in golden_results where actual_output is NULL.
    For direct evaluation without a prior execution, supply actual_output
    manually by calling judge_single.
    
    Returns aggregate stats + per-item results.
    """
    if client is None:
        client = AsyncOpenAI()

    # Fetch all items in the set
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
        # Check if there's an actual_output in golden_results for this item+agent
        existing = await pool.fetchrow(
            """
            SELECT id, actual_output FROM golden_results
            WHERE item_id = $1 AND agent_id = $2
            ORDER BY created_at DESC LIMIT 1
            """,
            item["id"], agent_id,
        )

        if not existing or not existing["actual_output"]:
            results.append({
                "item_id": str(item["id"]),
                "input_text": item["input_text"][:100],
                "score": None,
                "rationale": "No execution output found",
            })
            continue

        judgment = await judge_single(
            item["input_text"],
            item["expected_output"],
            existing["actual_output"],
            item["scoring_criteria"],
            client=client,
        )

        # Update the result row
        await pool.execute(
            """
            UPDATE golden_results
            SET score = $1, grading_rationale = $2, agent_version_label = $3
            WHERE id = $4
            """,
            judgment["score"],
            judgment["rationale"],
            agent_version_label,
            existing["id"],
        )

        scores.append(judgment["score"])
        results.append({
            "item_id": str(item["id"]),
            "input_text": item["input_text"][:100],
            "score": judgment["score"],
            "rationale": judgment["rationale"],
        })

    total = len(results)
    scored = len(scores)
    avg_score = sum(scores) / scored if scored else 0.0
    pass_rate = len([s for s in scores if s >= 0.7]) / scored if scored else 0.0

    candidate_version_id = None
    if workspace_id and user_id:
        # Regression & Auto-refinement check
        await check_regression_and_propose(
            pool=pool,
            golden_set_id=golden_set_id,
            agent_id=agent_id,
            new_avg_score=avg_score,
            results=results,
            workspace_id=workspace_id,
            user_id=user_id,
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
        )

        # Snapshot genome as CANDIDATE if pass_rate is acceptable and score improved
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
        "total_items": total,
        "scored_items": scored,
        "avg_score": round(avg_score, 3),
        "pass_rate": round(pass_rate, 3),
        "results": results,
        "candidate_version_id": str(candidate_version_id) if candidate_version_id else None,
    }

async def auto_eval_tick(ctx: dict) -> None:
    """Cron job that runs nightly to evaluate all workspaces against their golden datasets."""
    pool = ctx["pool"]
    workspaces = await pool.fetch("SELECT id FROM workspaces")
    client = AsyncOpenAI(api_key=os.environ.get("FLOW_OPENAI_API_KEY"))
    
    for ws in workspaces:
        ws_id = ws["id"]
        # Find active agent
        agent = await pool.fetchrow("SELECT id FROM agents WHERE workspace_id = $1 LIMIT 1", ws_id)
        if not agent:
            continue
        
        # Find golden set
        gset = await pool.fetchrow("SELECT id FROM golden_sets WHERE workspace_id = $1 LIMIT 1", ws_id)
        if not gset:
            continue
            
        logger.info("cron.auto_eval_tick.running workspace_id=%s agent_id=%s", ws_id, agent["id"])
        # Find a user to assign proposals to
        user = await pool.fetchrow("SELECT user_id FROM workspace_members WHERE workspace_id = $1 LIMIT 1", ws_id)
        user_id = user["user_id"] if user else None

        # Resolve current active genome version label (falls back to "v1.0" if none)
        active_genome = await get_active_genome(pool, agent["id"])
        version_label = active_genome.version_label if active_genome else "v1.0"

        try:
            await evaluate_golden_set(
                pool=pool,
                golden_set_id=gset["id"],
                agent_id=agent["id"],
                agent_version_label=version_label,
                workspace_id=ws_id,
                user_id=user_id,
                client=client,
            )
        except Exception as exc:
            logger.error("cron.auto_eval_tick.failed exc=%s workspace_id=%s", exc, ws_id)

