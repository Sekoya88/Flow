from __future__ import annotations

import json
import os
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI

from flow.application.curator import check_regression_and_propose
from flow.application.genome_service import _maybe_snapshot_eval_pass, get_active_genome
from flow.application.golden_evaluator import judge_single, run_agent_on_item
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

    stream_hub = getattr(request.app.state, "stream_hub", None)

    async def event_generator():
        def evt(kind: str, **payload) -> str:
            return f"data: {json.dumps({'kind': kind, **payload})}\n\n"

        yield evt("info", message="Initializing evaluation engine…")

        # Resolve workspace
        workspaces = await repo._pool.fetch(
            "SELECT w.id FROM workspaces w JOIN workspace_members wm ON wm.workspace_id = w.id WHERE wm.user_id = $1 LIMIT 1",
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
            row = await repo._pool.fetchrow("SELECT id FROM agents WHERE workspace_id = $1 LIMIT 1", workspace_id)
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
            row = await repo._pool.fetchrow("SELECT id FROM golden_sets WHERE workspace_id = $1 LIMIT 1", workspace_id)
            if not row:
                yield evt("error", message="No golden set found. Import sample datasets first.")
                yield evt("done", results=None)
                return
            resolved_set_id = row["id"]

        items = await repo._pool.fetch(
            "SELECT id, input_text, expected_output, scoring_criteria FROM golden_items WHERE set_id = $1 ORDER BY created_at",
            resolved_set_id,
        )
        if not items:
            yield evt("error", message="Golden set has no items.")
            yield evt("done", results=None)
            return

        yield evt("info", message=f"Running {len(items)} items through {llm_config['model']}…")

        if stream_hub:
            await stream_hub.publish_global(
                str(workspace_id),
                kind="eval.started",
                payload={
                    "agent_id": str(resolved_agent_id),
                    "golden_set_id": str(resolved_set_id),
                    "total": len(items),
                    "model": llm_config["model"],
                },
            )

        openai_key = os.environ.get("FLOW_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        judge_client = AsyncOpenAI(api_key=openai_key)
        eval_run_id = uuid4()
        results = []
        scores = []

        for i, item in enumerate(items):
            yield evt("progress", index=i, total=len(items), message=f"Item {i + 1}/{len(items)}: running agent…")

            # Real agent LLM call
            actual_output = await run_agent_on_item(
                input_text=item["input_text"],
                system_prompt=system_prompt,
                llm_config=llm_config,
                openai_api_key=openai_key,
                langsmith_extra={
                    "kind": "evaluation",
                    "workspace_id": str(workspace_id),
                    "agent_id": str(resolved_agent_id),
                    "golden_set_id": str(resolved_set_id),
                    "eval_run_id": str(eval_run_id),
                    "item_index": i,
                },
            )

            yield evt("progress", index=i, total=len(items), message=f"Item {i + 1}/{len(items)}: scoring with judge…")

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
            results.append(
                {
                    "item_id": str(item["id"]),
                    "input_text": item["input_text"][:120],
                    "actual_output": actual_output[:200],
                    "score": judgment["score"],
                    "rationale": judgment["rationale"],
                }
            )

            tick = "✓" if judgment["score"] >= 0.7 else "✗"
            yield evt(
                "item_result",
                index=i,
                score=judgment["score"],
                message=f"{tick} Item {i + 1}: {judgment['score']:.2f} — {judgment['rationale'][:80]}",
            )

        total = len(results)
        scored = len(scores)
        avg_score = sum(scores) / scored if scored else 0.0
        pass_rate = len([s for s in scores if s >= 0.7]) / scored if scored else 0.0

        yield evt(
            "summary",
            message=f"Done — pass rate: {pass_rate * 100:.1f}% | avg score: {avg_score:.3f}",
        )

        if stream_hub:
            await stream_hub.publish_global(
                str(workspace_id),
                kind="eval.done",
                payload={
                    "agent_id": str(resolved_agent_id),
                    "golden_set_id": str(resolved_set_id),
                    "total": total,
                    "scored": scored,
                    "avg_score": round(avg_score, 3),
                    "pass_rate": round(pass_rate, 3),
                },
            )

        if pass_rate < 0.7:
            yield evt("warning", message="REGRESSION — pass rate below 70% threshold")
        else:
            yield evt("success", message="Performance meets production criteria (≥70% pass rate)")

        # Post-eval hooks: regression proposal + genome snapshot + skill boost
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

            # Boost skill scores for items that passed and have a skill linkage
            try:
                passing_item_ids = [r["item_id"] for r in results if r["score"] >= 0.7]
                if passing_item_ids:
                    skill_rows = await repo._pool.fetch(
                        "SELECT DISTINCT skill_id FROM golden_items WHERE id = ANY($1::uuid[]) AND skill_id IS NOT NULL",
                        [r for r in passing_item_ids],
                    )
                    for sr in skill_rows:
                        await repo.boost_skill_score(sr["skill_id"])
            except Exception as boost_exc:
                import logging as _log

                _log.getLogger(__name__).debug("skill_boost_skipped: %s", boost_exc)

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


@router.get("/regression-report")
async def regression_report(
    request: Request,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    set_id: UUID | None = Query(default=None),
    agent_id: UUID | None = Query(default=None),
    runs: int = Query(default=5, ge=2, le=20),
) -> dict:
    """Compare the last N eval runs and identify per-item regressions.

    Returns a structured report showing:
    - Which items improved vs regressed between consecutive runs
    - Delta scores per item
    - Overall trend (improving/regressing/stable)
    """
    # Resolve workspace
    workspaces = await repo._pool.fetch(
        "SELECT w.id FROM workspaces w JOIN workspace_members wm ON wm.workspace_id = w.id WHERE wm.user_id = $1 LIMIT 1",
        user_id,
    )
    if not workspaces:
        workspaces = await repo._pool.fetch("SELECT id FROM workspaces LIMIT 1")
    if not workspaces:
        return {"error": "No workspace found"}
    workspace_id = workspaces[0]["id"]

    # Resolve set and agent
    resolved_set_id = set_id
    if not resolved_set_id:
        row = await repo._pool.fetchrow(
            "SELECT id FROM golden_sets WHERE workspace_id = $1 LIMIT 1",
            workspace_id,
        )
        if not row:
            return {"error": "No golden set found"}
        resolved_set_id = row["id"]

    resolved_agent_id = agent_id
    if not resolved_agent_id:
        row = await repo._pool.fetchrow(
            "SELECT id FROM agents WHERE workspace_id = $1 LIMIT 1",
            workspace_id,
        )
        if not row:
            return {"error": "No agent found"}
        resolved_agent_id = row["id"]

    # Get distinct eval runs (most recent first)
    run_rows = await repo._pool.fetch(
        """
        SELECT DISTINCT gr.eval_run_id, MIN(gr.created_at) AS run_at,
               gr.agent_version_label
        FROM golden_results gr
        JOIN golden_items gi ON gi.id = gr.item_id
        WHERE gi.set_id = $1 AND gr.agent_id = $2
          AND gr.eval_run_id IS NOT NULL AND gr.score IS NOT NULL
        GROUP BY gr.eval_run_id, gr.agent_version_label
        ORDER BY MIN(gr.created_at) DESC
        LIMIT $3
        """,
        resolved_set_id,
        resolved_agent_id,
        runs,
    )

    if len(run_rows) < 2:
        return {
            "status": "insufficient_data",
            "message": f"Need at least 2 eval runs, found {len(run_rows)}",
            "runs_available": len(run_rows),
        }

    # Reverse to chronological order
    run_rows = list(reversed(run_rows))

    # Fetch per-item scores for each run
    run_data = []
    for run in run_rows:
        items = await repo._pool.fetch(
            """
            SELECT gi.id AS item_id, gi.input_text, gr.score, gr.grading_rationale
            FROM golden_results gr
            JOIN golden_items gi ON gi.id = gr.item_id
            WHERE gr.eval_run_id = $1 AND gr.agent_id = $2
            ORDER BY gi.created_at
            """,
            run["eval_run_id"],
            resolved_agent_id,
        )
        scores_by_item = {}
        for it in items:
            scores_by_item[str(it["item_id"])] = {
                "score": it["score"],
                "input_text": it["input_text"][:120],
                "rationale": it["grading_rationale"],
            }
        run_data.append(
            {
                "run_id": str(run["eval_run_id"]),
                "run_at": run["run_at"].isoformat() if run["run_at"] else None,
                "version_label": run["agent_version_label"],
                "scores": scores_by_item,
            }
        )

    # Compare consecutive runs
    comparisons = []
    for i in range(1, len(run_data)):
        prev = run_data[i - 1]
        curr = run_data[i]
        all_items = set(prev["scores"].keys()) | set(curr["scores"].keys())

        improved = []
        regressed = []
        stable = []

        for item_id in all_items:
            prev_score = prev["scores"].get(item_id, {}).get("score")
            curr_score = curr["scores"].get(item_id, {}).get("score")
            if prev_score is None or curr_score is None:
                continue
            delta = curr_score - prev_score
            entry = {
                "item_id": item_id,
                "input_text": curr["scores"].get(item_id, prev["scores"].get(item_id, {})).get("input_text", ""),
                "prev_score": round(prev_score, 3),
                "curr_score": round(curr_score, 3),
                "delta": round(delta, 3),
            }
            if delta > 0.05:
                improved.append(entry)
            elif delta < -0.05:
                regressed.append(entry)
            else:
                stable.append(entry)

        prev_scores = [s["score"] for s in prev["scores"].values() if s["score"] is not None]
        curr_scores = [s["score"] for s in curr["scores"].values() if s["score"] is not None]
        prev_avg = sum(prev_scores) / len(prev_scores) if prev_scores else 0
        curr_avg = sum(curr_scores) / len(curr_scores) if curr_scores else 0

        comparisons.append(
            {
                "from_run": prev["run_id"],
                "to_run": curr["run_id"],
                "from_version": prev["version_label"],
                "to_version": curr["version_label"],
                "avg_delta": round(curr_avg - prev_avg, 3),
                "improved_count": len(improved),
                "regressed_count": len(regressed),
                "stable_count": len(stable),
                "improved": sorted(improved, key=lambda x: -x["delta"]),
                "regressed": sorted(regressed, key=lambda x: x["delta"]),
            }
        )

    # Overall trend
    if len(comparisons) >= 2:
        recent_deltas = [c["avg_delta"] for c in comparisons[-3:]]
        avg_trend = sum(recent_deltas) / len(recent_deltas)
        if avg_trend > 0.02:
            trend = "improving"
        elif avg_trend < -0.02:
            trend = "regressing"
        else:
            trend = "stable"
    else:
        trend = "insufficient_data"

    return {
        "status": "ok",
        "agent_id": str(resolved_agent_id),
        "golden_set_id": str(resolved_set_id),
        "runs_compared": len(run_data),
        "trend": trend,
        "comparisons": comparisons,
    }


@router.post("/improve")
async def trigger_improvement(
    request: Request,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    set_id: UUID | None = Query(default=None),
    agent_id: UUID | None = Query(default=None),
) -> dict:
    """Trigger the autonomous improvement loop on demand.

    Runs a fresh evaluation, then calls the Prompt Rewriter to generate
    an improved system prompt based on failures. Creates a CANDIDATE
    genome and a proposal for human approval.

    This is the "one-click improve" action.
    """
    # Resolve workspace
    workspaces = await repo._pool.fetch(
        "SELECT w.id FROM workspaces w JOIN workspace_members wm ON wm.workspace_id = w.id WHERE wm.user_id = $1 LIMIT 1",
        user_id,
    )
    if not workspaces:
        return {"error": "No workspace found"}
    workspace_id = workspaces[0]["id"]

    # Resolve agent
    resolved_agent_id = agent_id
    if not resolved_agent_id:
        row = await repo._pool.fetchrow(
            "SELECT id FROM agents WHERE workspace_id = $1 LIMIT 1",
            workspace_id,
        )
        if not row:
            return {"error": "No agent found"}
        resolved_agent_id = row["id"]

    # Load active genome
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

    # Resolve golden set
    resolved_set_id = set_id
    if not resolved_set_id:
        row = await repo._pool.fetchrow(
            "SELECT id FROM golden_sets WHERE workspace_id = $1 LIMIT 1",
            workspace_id,
        )
        if not row:
            return {"error": "No golden set found"}
        resolved_set_id = row["id"]

    openai_key = os.environ.get("FLOW_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")

    # Run fresh evaluation
    from flow.application.golden_evaluator import evaluate_golden_set

    eval_result = await evaluate_golden_set(
        pool=repo._pool,
        golden_set_id=resolved_set_id,
        agent_id=resolved_agent_id,
        agent_version_label=agent_version,
        workspace_id=workspace_id,
        user_id=user_id,
        system_prompt=system_prompt,
        llm_config=llm_config,
        openai_api_key=openai_key,
    )

    # Get failures
    failed_items = [r for r in eval_result["results"] if r["score"] < 0.7]

    if not failed_items:
        return {
            "status": "no_improvement_needed",
            "message": "All items passed (≥0.7). Agent is performing well.",
            "eval_run_id": eval_result["eval_run_id"],
            "avg_score": eval_result["avg_score"],
            "pass_rate": eval_result["pass_rate"],
        }

    # Run prompt rewriter
    from flow.application.prompt_rewriter import FailedItem, rewrite_and_snapshot

    failed_for_rewrite = [
        FailedItem(
            input_text=r.get("input_text", ""),
            expected_output=r.get("expected_output", ""),
            actual_output=r.get("actual_output", ""),
            score=r["score"],
            rationale=r.get("rationale", ""),
        )
        for r in failed_items
    ]

    rewrite_info = await rewrite_and_snapshot(
        pool=repo._pool,
        agent_id=resolved_agent_id,
        workspace_id=workspace_id,
        user_id=user_id,
        current_prompt=system_prompt,
        failed_items=failed_for_rewrite,
        llm_config=llm_config,
        openai_api_key=openai_key,
    )

    if not rewrite_info:
        return {
            "status": "rewrite_skipped",
            "message": "Prompt rewriter could not produce a confident improvement.",
            "eval_run_id": eval_result["eval_run_id"],
            "num_failures": len(failed_items),
        }

    return {
        "status": "candidate_created",
        "message": "Improved prompt created as candidate genome. Check Proposals to approve.",
        "eval_run_id": eval_result["eval_run_id"],
        "avg_score": eval_result["avg_score"],
        "pass_rate": eval_result["pass_rate"],
        "num_failures": len(failed_items),
        **rewrite_info,
    }
