"""Autonomous evolution & snapshot routes — Phase 3b + Phase 4a.

Adds:
- POST /api/v1/agents/{id}/evolve — trigger one evolution cycle
- POST /api/v1/agents/{id}/snapshot — capture full agent state
- POST /api/v1/agents/{id}/restore-snapshot — restore from snapshot JSON
- GET /api/v1/agents/{id}/metacog — metacognitive journal
- GET /api/v1/agents/{id}/bandit — bandit arm stats
- GET /api/v1/agents/{id}/rl-episodes — RL episode history
"""

from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo

router = APIRouter(prefix="/api/v1/agents/{agent_id}", tags=["evolution"])


class EvolveIn(BaseModel):
    score_threshold: float = 0.7
    max_mutations: int = 3


class RestoreSnapshotIn(BaseModel):
    snapshot_json: str


# ── helpers ──


async def _get_agent(repo: FlowRepository, agent_id: UUID, user_id: UUID):
    ws_rows = await repo.list_workspaces_for_user(user_id)
    for r in ws_rows:
        agent = await repo.get_agent(agent_id, r["id"])
        if agent:
            return agent
    raise HTTPException(status_code=404, detail="agent not found")


# ── Evolution ──


@router.post("/evolve")
async def trigger_evolution(
    agent_id: UUID,
    body: EvolveIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Trigger one genome evolution cycle for this agent."""
    agent = await _get_agent(repo, agent_id, user_id)
    workspace_id = agent["workspace_id"]

    from flow.application.genome_evolver import GenomeEvolver

    evolver = GenomeEvolver(repo._pool)
    result = await evolver.run_evolution_cycle(
        agent_id=agent_id,
        workspace_id=workspace_id,
        score_threshold=body.score_threshold,
        max_mutations=body.max_mutations,
    )

    return {
        "cycle_status": result.cycle_status,
        "current_score": result.current_score,
        "candidate_score": result.candidate_score,
        "mutation_type": result.mutation_type,
        "candidate_genome_id": str(result.candidate_genome_id) if result.candidate_genome_id else None,
        "details": result.details,
    }


# ── Snapshots ──


@router.post("/snapshot")
async def capture_snapshot(
    agent_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> Response:
    """Capture a full, portable snapshot of the agent's current state."""
    agent = await _get_agent(repo, agent_id, user_id)
    workspace_id = agent["workspace_id"]

    from flow.application.workflow_snapshot import WorkflowSnapshot

    snap = WorkflowSnapshot(repo._pool)
    payload = await snap.capture(agent_id, workspace_id)
    json_str = snap.export_json(payload)

    return Response(
        content=json_str,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="flow-snapshot-{agent_id}-{payload.captured_at[:10]}.json"',
        },
    )


@router.post("/restore-snapshot")
async def restore_snapshot(
    agent_id: UUID,
    body: RestoreSnapshotIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Restore an agent from a snapshot JSON."""
    await _get_agent(repo, agent_id, user_id)

    from flow.application.workflow_snapshot import WorkflowSnapshot

    snap = WorkflowSnapshot(repo._pool)
    payload = snap.from_json(body.snapshot_json)

    # Ensure the snapshot belongs to this agent
    if payload.agent_id != agent_id:
        raise HTTPException(status_code=400, detail="snapshot agent_id does not match")

    genome_id = await snap.restore(payload)
    if genome_id is None:
        raise HTTPException(status_code=500, detail="failed to restore snapshot")

    return {
        "restored_genome_id": str(genome_id),
        "snapshot_id": str(payload.snapshot_id),
        "captured_at": payload.captured_at,
    }


# ── MetaCog ──


@router.get("/metacog")
async def get_metacog_journal(
    agent_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    limit: int = 20,
) -> dict:
    """Fetch metacognitive journal entries for this agent."""
    agent = await _get_agent(repo, agent_id, user_id)
    workspace_id = agent["workspace_id"]

    from flow.application.metacog_service import MetaCogService

    metacog = MetaCogService(repo._pool)
    journal = await metacog.get_journal(agent_id, workspace_id, limit=limit)
    cal_stats = await metacog.get_calibration_stats(agent_id, workspace_id)

    return {
        "journal": [
            {
                "id": str(e["id"]),
                "execution_id": str(e["execution_id"]) if e.get("execution_id") else None,
                "grade": e["grade"],
                "prediction": e.get("prediction"),
                "calibration_error": float(e.get("calibration_error") or 0),
                "skill_scores": e.get("skill_scores"),
                "mutations_proposed": e.get("mutations_proposed"),
                "reasoning": e.get("reasoning"),
                "created_at": e["created_at"].isoformat() if e.get("created_at") else None,
            }
            for e in journal
        ],
        "calibration": cal_stats,
    }


# ── Bandit ──


@router.get("/bandit")
async def get_bandit_stats(
    agent_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Get Thompson Sampling bandit arm stats for this agent."""
    await _get_agent(repo, agent_id, user_id)

    from flow.application.rl_bandit import SkillBandit

    bandit = SkillBandit(repo._pool)
    arms = await bandit.get_arm_stats(agent_id)

    return {
        "arms": [
            {
                "skill_id": str(a.skill_id),
                "skill_name": a.skill_name,
                "alpha": a.alpha,
                "beta": a.beta,
                "mean": round(a.mean, 4),
                "total_pulls": a.total_pulls,
                "total_reward": round(a.total_reward, 3),
            }
            for a in arms.values()
        ],
    }


# ── RL Episodes ──


@router.get("/rl-episodes")
async def get_rl_episodes(
    agent_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    limit: int = 30,
) -> dict:
    """Get RL episode history for this agent."""
    await _get_agent(repo, agent_id, user_id)

    try:
        rows = await repo._pool.fetch(
            """
            SELECT id, parent_genome_id, candidate_genome_id, mutation_type,
                   reward_before, reward_after, reward_delta, promoted, created_at
            FROM rl_episodes
            WHERE agent_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            agent_id,
            limit,
        )
        episodes = [
            {
                "id": str(r["id"]),
                "parent_genome_id": str(r["parent_genome_id"]) if r["parent_genome_id"] else None,
                "candidate_genome_id": str(r["candidate_genome_id"]) if r["candidate_genome_id"] else None,
                "mutation_type": r["mutation_type"],
                "reward_before": float(r["reward_before"] or 0),
                "reward_after": float(r["reward_after"] or 0),
                "reward_delta": float(r["reward_delta"] or 0),
                "promoted": bool(r["promoted"]),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    except Exception:
        episodes = []

    return {"episodes": episodes}
