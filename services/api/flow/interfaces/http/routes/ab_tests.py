"""A/B testing: compare two agents head-to-head on a shared golden set."""
from __future__ import annotations

import json
import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from flow.application.genome_service import get_active_genome
from flow.application.golden_evaluator import judge_single, run_agent_on_item
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo
from flow.interfaces.http.schemas import ABTestCreateIn

router = APIRouter(prefix="/api/v1/ab-tests", tags=["ab-tests"])


@router.post("")
async def create_ab_test(
    body: ABTestCreateIn,
    background_tasks: BackgroundTasks,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Create an A/B test and start it asynchronously."""
    ws_rows = await repo.list_workspaces_for_user(user_id)
    if not ws_rows:
        raise HTTPException(status_code=404, detail="no workspace")
    ws_id = ws_rows[0]["id"]

    # Verify golden set belongs to workspace
    gs = await repo._pool.fetchrow(
        "SELECT id FROM golden_sets WHERE id=$1 AND workspace_id=$2",
        body.golden_set_id, ws_id,
    )
    if not gs:
        raise HTTPException(status_code=404, detail="golden set not found")

    test_id = await repo._pool.fetchval(
        """
        INSERT INTO ab_tests (workspace_id, golden_set_id, agent_a_id, agent_a_version, agent_b_id, agent_b_version, status)
        VALUES ($1,$2,$3,$4,$5,$6,'pending') RETURNING id
        """,
        ws_id, body.golden_set_id,
        body.agent_a_id, body.agent_a_version or None,
        body.agent_b_id, body.agent_b_version or None,
    )

    async def _run():
        await _run_ab_test(repo._pool, test_id, body.golden_set_id, body.agent_a_id, body.agent_b_id)

    background_tasks.add_task(_run)
    return {"id": str(test_id), "status": "pending"}


@router.get("")
async def list_ab_tests(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    if not ws_rows:
        return {"tests": []}
    ws_id = ws_rows[0]["id"]
    rows = await repo._pool.fetch(
        """
        SELECT t.id, t.status, t.created_at,
               t.agent_a_version, t.agent_b_version,
               aa.name AS agent_a_name, ab.name AS agent_b_name,
               gs.name AS set_name
        FROM ab_tests t
        JOIN agents aa ON aa.id = t.agent_a_id
        JOIN agents ab ON ab.id = t.agent_b_id
        JOIN golden_sets gs ON gs.id = t.golden_set_id
        WHERE t.workspace_id = $1
        ORDER BY t.created_at DESC
        LIMIT 20
        """,
        ws_id,
    )
    return {
        "tests": [
            {
                "id": str(r["id"]),
                "status": r["status"],
                "agent_a": r["agent_a_name"],
                "agent_a_version": r["agent_a_version"],
                "agent_b": r["agent_b_name"],
                "agent_b_version": r["agent_b_version"],
                "golden_set": r["set_name"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


@router.get("/{test_id}")
async def get_ab_test(
    test_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    if not ws_rows:
        raise HTTPException(status_code=404)
    ws_id = ws_rows[0]["id"]

    test = await repo._pool.fetchrow(
        """
        SELECT t.*, aa.name AS agent_a_name, ab.name AS agent_b_name, gs.name AS set_name
        FROM ab_tests t
        JOIN agents aa ON aa.id = t.agent_a_id
        JOIN agents ab ON ab.id = t.agent_b_id
        JOIN golden_sets gs ON gs.id = t.golden_set_id
        WHERE t.id=$1 AND t.workspace_id=$2
        """,
        test_id, ws_id,
    )
    if not test:
        raise HTTPException(status_code=404, detail="ab test not found")

    # Fetch results
    results = await repo._pool.fetch(
        """
        SELECT r.id, r.agent_label, r.score, r.grading_rationale, r.actual_output,
               gi.input_text, gi.expected_output
        FROM ab_test_results r
        JOIN golden_items gi ON gi.id = r.golden_item_id
        WHERE r.test_id=$1
        ORDER BY gi.created_at, r.agent_label
        """,
        test_id,
    )

    a_scores = [r["score"] for r in results if r["agent_label"] == "A" and r["score"] is not None]
    b_scores = [r["score"] for r in results if r["agent_label"] == "B" and r["score"] is not None]

    return {
        "id": str(test["id"]),
        "status": test["status"],
        "agent_a": {"name": test["agent_a_name"], "version": test["agent_a_version"]},
        "agent_b": {"name": test["agent_b_name"], "version": test["agent_b_version"]},
        "golden_set": test["set_name"],
        "aggregate": {
            "agent_a_avg": round(sum(a_scores) / len(a_scores), 3) if a_scores else 0.0,
            "agent_b_avg": round(sum(b_scores) / len(b_scores), 3) if b_scores else 0.0,
            "winner": "A" if (sum(a_scores) / len(a_scores) if a_scores else 0) > (sum(b_scores) / len(b_scores) if b_scores else 0) else "B",
        },
        "results": [
            {
                "item_id": str(r["id"]),
                "agent_label": r["agent_label"],
                "score": r["score"],
                "rationale": r["grading_rationale"],
                "actual_output": (r["actual_output"] or "")[:300],
                "input_text": r["input_text"][:100],
            }
            for r in results
        ],
        "created_at": test["created_at"].isoformat(),
    }


# ── Background task ───────────────────────────────────────────────────

async def _get_agent_config(pool, agent_id: UUID) -> dict:
    """Return system_prompt + llm_config for an agent via its active genome."""
    genome = await get_active_genome(pool, agent_id)
    if genome:
        return {
            "system_prompt": genome.system_prompt or "",
            "llm_config": {
                "provider": genome.llm_config.provider,
                "model": genome.llm_config.model,
                "temperature": genome.llm_config.temperature,
            },
        }
    # Fallback: read from agents.config JSON blob
    row = await pool.fetchrow("SELECT config FROM agents WHERE id = $1", agent_id)
    if row and row["config"]:
        raw = row["config"]
        cfg = json.loads(raw) if isinstance(raw, str) else dict(raw)
        return {
            "system_prompt": cfg.get("system_prompt", ""),
            "llm_config": cfg.get("llm_config") or cfg.get("model") or {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.3},
        }
    return {"system_prompt": "", "llm_config": {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.3}}


async def _run_ab_test(pool, test_id: UUID, golden_set_id: UUID, agent_a_id: UUID, agent_b_id: UUID):
    """Run both agents on golden items and judge head-to-head."""
    await pool.execute("UPDATE ab_tests SET status='running' WHERE id=$1", test_id)

    try:
        from openai import AsyncOpenAI

        openai_key = os.environ.get("FLOW_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        anthropic_key = os.environ.get("FLOW_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        client = AsyncOpenAI(api_key=openai_key) if openai_key else AsyncOpenAI()

        items = await pool.fetch(
            "SELECT id, input_text, expected_output, scoring_criteria FROM golden_items WHERE set_id=$1 ORDER BY created_at",
            golden_set_id,
        )

        # Fetch agent configs once upfront
        cfg_a = await _get_agent_config(pool, agent_a_id)
        cfg_b = await _get_agent_config(pool, agent_b_id)
        agent_cfgs = {"A": cfg_a, "B": cfg_b}
        agent_ids = {"A": agent_a_id, "B": agent_b_id}

        for item in items:
            for label in ("A", "B"):
                agent_id = agent_ids[label]
                cfg = agent_cfgs[label]

                # Use the most recent golden_result if available (fast path), else run the agent
                cached = await pool.fetchrow(
                    """
                    SELECT actual_output FROM golden_results
                    WHERE item_id=$1 AND agent_id=$2 AND actual_output IS NOT NULL
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    item["id"], agent_id,
                )
                if cached:
                    actual_output = cached["actual_output"]
                else:
                    actual_output = await run_agent_on_item(
                        input_text=item["input_text"],
                        system_prompt=cfg["system_prompt"],
                        llm_config=cfg["llm_config"],
                        openai_api_key=openai_key,
                        anthropic_api_key=anthropic_key,
                    )

                judgment = await judge_single(
                    item["input_text"],
                    item["expected_output"],
                    actual_output,
                    item["scoring_criteria"],
                    client=client,
                )
                await pool.execute(
                    """
                    INSERT INTO ab_test_results (test_id, golden_item_id, agent_label, score, actual_output, grading_rationale)
                    VALUES ($1,$2,$3,$4,$5,$6)
                    """,
                    test_id, item["id"], label,
                    judgment["score"], actual_output, judgment["rationale"],
                )

        await pool.execute("UPDATE ab_tests SET status='completed' WHERE id=$1", test_id)
    except Exception:
        await pool.execute("UPDATE ab_tests SET status='failed' WHERE id=$1", test_id)
        raise
