from __future__ import annotations

import json
import os
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI

from flow.application.genome_service import get_active_genome, _maybe_snapshot_eval_pass
from flow.application.golden_evaluator import judge_single, run_agent_on_item
from flow.application.curator import check_regression_and_propose
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


@router.get("/run")
async def run_evaluation_sse(
    request: Request,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    set_id: UUID | None = Query(default=None),
    agent_id: UUID | None = Query(default=None),
) -> StreamingResponse:
    """Run golden evaluation and stream logs via SSE.

    Runs the agent's own LLM (using its active genome config) on each golden
    item, scores with LLM-as-judge, INSERTs new golden_results rows, then
    checks for regression and genome improvement.
    """

    async def event_generator():
        def evt(kind: str, **payload) -> str:
            return f"data: {json.dumps({'kind': kind, **payload})}\n\n"

        yield evt("info", message="Initializing evaluation engine…")

        # Resolve workspace
        workspaces = await repo._pool.fetch(
            "SELECT w.id FROM workspaces w "
            "JOIN workspace_members wm ON wm.workspace_id = w.id "
            "WHERE wm.user_id = $1 LIMIT 1",
            user_id,
        )
        if not workspaces:
            workspaces = await repo._pool.fetch("SELECT id FROM workspaces LIMIT 1")
        if not workspaces:
            yield evt("error", message="No workspace found")
            yield evt("done", results=None)
            return
        workspace_id = workspaces[0]["id"]

        # Resolve agent
        resolved_agent_id = agent_id
        if resolved_agent_id is None:
            row = await repo._pool.fetchrow(
                "SELECT id FROM agents WHERE workspace_id = $1 LIMIT 1", workspace_id
            )
            if not row:
                yield evt("error", message="No agent found in workspace")
                yield evt("done", results=None)
                return
            resolved_agent_id = row["id"]

        # Load active genome — drives the actual LLM call
        active_genome = await get_active_genome(repo._pool, resolved_agent_id)
        agent_version = active_genome.version_label if active_genome else "v1.0"
        system_prompt = active_genome.system_prompt if active_genome else ""
        llm_config = (
            {
                "provider": active_genome.llm_config.provider,
                "model": active_genome.llm_config.model,
                "temperature": active_genome.llm_config.temperature,
            }
            if active_genome
            else {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.3}
        )

        yield evt("info", message=f"Genome: {agent_version} | model: {llm_config['model']}")

        # Resolve golden set
        resolved_set_id = set_id
        if resolved_set_id is None:
            row = await repo._pool.fetchrow(
                "SELECT id FROM golden_sets WHERE workspace_id = $1 LIMIT 1", workspace_id
            )
            if not row:
                yield evt("error", message="No golden set found. Import sample datasets first.")
                yield evt("done", results=None)
                return
            resolved_set_id = row["id"]

        items = await repo._pool.fetch(
            "SELECT id, input_text, expected_output, scoring_criteria FROM golden_items "
            "WHERE set_id = $1 ORDER BY created_at",
            resolved_set_id,
        )
        if not items:
            yield evt("error", message="Golden set has no items.")
            yield evt("done", results=None)
            return

        yield evt("info", message=f"Running {len(items)} items through {llm_config['model']}…")

        openai_key = os.environ.get("FLOW_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        judge_client = AsyncOpenAI(api_key=openai_key)
        eval_run_id = uuid4()
        results = []
        scores = []

        for i, item in enumerate(items):
            yield evt("progress", index=i, total=len(items),
                      message=f"Item {i+1}/{len(items)}: running agent…")

            # Real agent LLM call
            actual_output = await run_agent_on_item(
                input_text=item["input_text"],
                system_prompt=system_prompt,
                llm_config=llm_config,
                openai_api_key=openai_key,
            )

            yield evt("progress", index=i, total=len(items),
                      message=f"Item {i+1}/{len(items)}: scoring with judge…")

            # Score
            judgment = await judge_single(
                item["input_text"],
                item["expected_output"],
                actual_output,
                item["scoring_criteria"],
                client=judge_client,
            )

            # Always INSERT — builds history across runs
            await repo._pool.execute(
                """
                INSERT INTO golden_results
                    (item_id, agent_id, agent_version_label, actual_output,
                     score, grading_rationale, eval_run_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                item["id"],
                resolved_agent_id,
                agent_version,
                actual_output,
                judgment["score"],
                judgment["rationale"],
                eval_run_id,
            )

            scores.append(judgment["score"])
            results.append({
                "item_id": str(item["id"]),
                "input_text": item["input_text"][:120],
                "actual_output": actual_output[:200],
                "score": judgment["score"],
                "rationale": judgment["rationale"],
            })

            tick = "✓" if judgment["score"] >= 0.7 else "✗"
            yield evt(
                "item_result",
                index=i,
                score=judgment["score"],
                message=f"{tick} Item {i+1}: {judgment['score']:.2f} — {judgment['rationale'][:80]}",
            )

        total = len(results)
        scored = len(scores)
        avg_score = sum(scores) / scored if scored else 0.0
        pass_rate = len([s for s in scores if s >= 0.7]) / scored if scored else 0.0

        yield evt(
            "summary",
            message=f"Done — pass rate: {pass_rate*100:.1f}% | avg score: {avg_score:.3f}",
        )

        if pass_rate < 0.7:
            yield evt("warning", message="REGRESSION — pass rate below 70% threshold")
        else:
            yield evt("success", message="Performance meets production criteria (≥70% pass rate)")

        # Post-eval hooks: regression proposal + genome snapshot
        candidate_version_id = None
        try:
            await check_regression_and_propose(
                pool=repo._pool,
                golden_set_id=resolved_set_id,
                agent_id=resolved_agent_id,
                new_avg_score=avg_score,
                results=results,
                workspace_id=workspace_id,
                user_id=user_id,
                openai_api_key=openai_key,
            )
            if pass_rate >= 0.7:
                candidate_version_id = await _maybe_snapshot_eval_pass(
                    pool=repo._pool,
                    agent_id=resolved_agent_id,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    avg_score=avg_score,
                    pass_rate=pass_rate,
                )
                if candidate_version_id:
                    yield evt(
                        "info",
                        message="Score improved — genome candidate created. Check Proposals to promote.",
                    )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("post_eval_hooks failed: %s", exc)

        yield evt(
            "done",
            results={
                "eval_run_id": str(eval_run_id),
                "total_items": total,
                "scored_items": scored,
                "avg_score": round(avg_score, 3),
                "pass_rate": round(pass_rate, 3),
                "results": results,
                "candidate_version_id": str(candidate_version_id) if candidate_version_id else None,
            },
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
