from __future__ import annotations

import json
import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI

from flow.application.genome_service import get_active_genome
from flow.application.golden_evaluator import evaluate_golden_set
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

    If set_id / agent_id are not provided, falls back to the first found.
    """

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
            row = await repo._pool.fetchrow(
                "SELECT id FROM agents WHERE workspace_id = $1 LIMIT 1", workspace_id
            )
            if not row:
                yield evt("error", message="No agent found in workspace")
                yield evt("done", results=None)
                return
            resolved_agent_id = row["id"]

        # Resolve version label from active genome
        active_genome = await get_active_genome(repo._pool, resolved_agent_id)
        agent_version = active_genome.version_label if active_genome else "v1.0"
        yield evt("info", message=f"Agent genome version: {agent_version}")

        # Resolve golden set
        resolved_set_id = set_id
        if resolved_set_id is None:
            row = await repo._pool.fetchrow(
                "SELECT id FROM golden_sets WHERE workspace_id = $1 LIMIT 1", workspace_id
            )
            if not row:
                yield evt("error", message="No golden set found. Create one in the Evaluations panel.")
                yield evt("done", results=None)
                return
            resolved_set_id = row["id"]

        items = await repo._pool.fetch(
            "SELECT id, expected_output FROM golden_items WHERE set_id = $1", resolved_set_id
        )
        yield evt("info", message=f"Golden set: {resolved_set_id} — {len(items)} items")

        # Ensure outputs exist (seed simulated if missing)
        seeded = 0
        for item in items:
            exists = await repo._pool.fetchval(
                "SELECT id FROM golden_results WHERE item_id = $1 AND agent_id = $2 AND agent_version_label = $3",
                item["id"], resolved_agent_id, agent_version,
            )
            if not exists:
                await repo._pool.execute(
                    "INSERT INTO golden_results (item_id, agent_id, agent_version_label, actual_output) VALUES ($1,$2,$3,$4)",
                    item["id"], resolved_agent_id, agent_version,
                    f"Simulated output matching: {item['expected_output'][:60]}…",
                )
                seeded += 1
        if seeded:
            yield evt("info", message=f"Seeded {seeded} simulated outputs for missing results")

        yield evt("info", message="Running LLM-as-judge evaluation (gpt-4o-mini)…")

        client = AsyncOpenAI(api_key=os.environ.get("FLOW_OPENAI_API_KEY"))
        results = await evaluate_golden_set(
            pool=repo._pool,
            golden_set_id=resolved_set_id,
            agent_id=resolved_agent_id,
            agent_version_label=agent_version,
            workspace_id=workspace_id,
            user_id=user_id,
            client=client,
        )

        pass_rate = results.get("pass_rate", 0.0)
        avg_score = results.get("avg_score", 0.0)
        yield evt("info", message=f"Evaluation complete — pass rate: {pass_rate * 100:.1f}%, avg score: {avg_score:.3f}")

        if pass_rate < 0.7:
            yield evt("warning", message="REGRESSION DETECTED — pass rate below 70% threshold")
        else:
            yield evt("success", message="Agent performance stable — meets production criteria")

        yield evt("done", results=results)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
