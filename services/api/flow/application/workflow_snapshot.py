"""Workflow Snapshot — Phase 4a.

Captures and restores a complete, reproducible snapshot of an agent's
execution state, including genome, skills, metacog state, bandit arms,
and recent traces.

Enables:
- Reproducible debugging (restore exact agent state that produced a run)
- Genome lineage inspection (export full state at any version)
- Portable agent transfer (export → import in another Flow instance)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


@dataclass
class SnapshotPayload:
    """Complete, serializable agent state snapshot."""

    snapshot_id: UUID
    agent_id: UUID
    workspace_id: UUID
    captured_at: str  # ISO 8601

    # Core genome
    genome: dict[str, Any]

    # Active skills (full SKILL.md content)
    skills: list[dict[str, Any]]

    # MetaCog state
    metacog_journal: list[dict[str, Any]]
    calibration_stats: dict[str, float]

    # Bandit arms (Phase 3a)
    bandit_arms: list[dict[str, Any]]

    # Recent execution traces
    recent_traces: list[dict[str, Any]]

    # RL episodes
    rl_episodes: list[dict[str, Any]]

    # Metadata
    flow_version: str = "2.0.0"
    snapshot_format: int = 1


class WorkflowSnapshot:
    """Capture and restore complete agent snapshots."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def capture(
        self,
        agent_id: UUID,
        workspace_id: UUID,
        *,
        max_traces: int = 5,
        max_journal: int = 10,
        max_episodes: int = 20,
    ) -> SnapshotPayload:
        """Capture a full snapshot of the agent's current state."""
        from flow.application.genome_service import get_active_genome

        # 1. Current genome
        genome = await get_active_genome(self._pool, agent_id)
        genome_dict = genome.to_jsonb_dict() if genome else {}

        # 2. Active skills
        skills = []
        try:
            rows = await self._pool.fetch(
                """
                SELECT id, name, content_md, score, use_count, version, created_at
                FROM agent_skills
                WHERE agent_id = $1 AND workspace_id = $2 AND active = TRUE
                ORDER BY score DESC
                """,
                agent_id,
                workspace_id,
            )
            skills = [
                {
                    "id": str(r["id"]),
                    "name": r["name"],
                    "content_md": r["content_md"],
                    "score": float(r["score"] or 0),
                    "use_count": int(r["use_count"] or 0),
                    "version": int(r["version"] or 1),
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]
        except Exception:
            logger.debug("snapshot.skills_fetch_failed", exc_info=True)

        # 3. MetaCog journal
        journal = []
        try:
            rows = await self._pool.fetch(
                """
                SELECT id, execution_id, grade, prediction, calibration_error,
                       skill_scores, mutations_proposed, reasoning, created_at
                FROM metacog_journal
                WHERE agent_id = $1 AND workspace_id = $2
                ORDER BY created_at DESC
                LIMIT $3
                """,
                agent_id,
                workspace_id,
                max_journal,
            )
            journal = [
                {
                    "id": str(r["id"]),
                    "execution_id": str(r["execution_id"]) if r["execution_id"] else None,
                    "grade": r["grade"],
                    "prediction": r["prediction"],
                    "calibration_error": float(r["calibration_error"] or 0),
                    "skill_scores": r["skill_scores"],
                    "mutations_proposed": r["mutations_proposed"],
                    "reasoning": r["reasoning"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]
        except Exception:
            pass  # table may not exist yet

        # 4. Calibration stats
        cal_stats = {"avg_error": 0.0, "std_error": 0.0, "total_entries": 0, "avg_grade": 0.0}
        try:
            from flow.application.metacog_service import MetaCogService

            metacog = MetaCogService(self._pool)
            cal_stats = await metacog.get_calibration_stats(agent_id, workspace_id)
        except Exception:
            pass

        # 5. Bandit arms
        bandit_arms = []
        try:
            rows = await self._pool.fetch(
                """
                SELECT ba.skill_id, ba.alpha, ba.beta, ba.total_pulls, ba.total_reward, ba.updated_at,
                       COALESCE(s.name, 'unknown') AS skill_name
                FROM skill_bandit_arms ba
                LEFT JOIN agent_skills s ON s.id = ba.skill_id
                WHERE ba.agent_id = $1
                """,
                agent_id,
            )
            bandit_arms = [
                {
                    "skill_id": str(r["skill_id"]),
                    "skill_name": r["skill_name"],
                    "alpha": float(r["alpha"]),
                    "beta": float(r["beta"]),
                    "total_pulls": int(r["total_pulls"]),
                    "total_reward": float(r["total_reward"]),
                    "mean": float(r["alpha"]) / (float(r["alpha"]) + float(r["beta"])),
                    "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
                }
                for r in rows
            ]
        except Exception:
            pass  # table may not exist yet

        # 6. Recent traces
        recent_traces = []
        try:
            rows = await self._pool.fetch(
                """
                SELECT id, user_message, answer, confidence, created_at
                FROM executions
                WHERE agent_id = $1 AND workspace_id = $2
                ORDER BY created_at DESC
                LIMIT $3
                """,
                agent_id,
                workspace_id,
                max_traces,
            )
            recent_traces = [
                {
                    "id": str(r["id"]),
                    "user_message": (r.get("user_message") or "")[:500],
                    "answer": (r.get("answer") or "")[:1000],
                    "confidence": float(r.get("confidence") or 0),
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]
        except Exception:
            pass

        # 7. RL episodes
        rl_episodes = []
        try:
            rows = await self._pool.fetch(
                """
                SELECT id, parent_genome_id, candidate_genome_id, mutation_type,
                       reward_before, reward_after, reward_delta, promoted, created_at
                FROM rl_episodes
                WHERE agent_id = $1 AND workspace_id = $2
                ORDER BY created_at DESC
                LIMIT $3
                """,
                agent_id,
                workspace_id,
                max_episodes,
            )
            rl_episodes = [
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
            pass

        return SnapshotPayload(
            snapshot_id=uuid4(),
            agent_id=agent_id,
            workspace_id=workspace_id,
            captured_at=datetime.utcnow().isoformat() + "Z",
            genome=genome_dict,
            skills=skills,
            metacog_journal=journal,
            calibration_stats=cal_stats,
            bandit_arms=bandit_arms,
            recent_traces=recent_traces,
            rl_episodes=rl_episodes,
        )

    async def restore(self, snapshot: SnapshotPayload) -> UUID | None:
        """Restore an agent to a snapshot state.

        Creates a new CANDIDATE genome version matching the snapshot,
        and restores bandit arm stats.
        Returns the new genome version ID, or None on failure.
        """
        try:
            from flow.application.genome_service import snapshot_genome
            from flow.domain.genome import VersionStatus, VersionTrigger

            # Create new genome version from snapshot
            genome_id = await snapshot_genome(
                pool=self._pool,
                agent_id=snapshot.agent_id,
                workspace_id=snapshot.workspace_id,
                trigger=VersionTrigger.MANUAL,
                created_by=None,
                status=VersionStatus.CANDIDATE,
                system_prompt_override=snapshot.genome.get("system_prompt"),
            )

            # Restore bandit arm stats
            for arm in snapshot.bandit_arms:
                try:
                    await self._pool.execute(
                        """
                        INSERT INTO skill_bandit_arms (skill_id, agent_id, alpha, beta, total_pulls, total_reward)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (skill_id, agent_id) DO UPDATE SET
                            alpha = $3, beta = $4, total_pulls = $5, total_reward = $6,
                            updated_at = now()
                        """,
                        UUID(arm["skill_id"]),
                        snapshot.agent_id,
                        arm["alpha"],
                        arm["beta"],
                        arm["total_pulls"],
                        arm["total_reward"],
                    )
                except Exception:
                    pass

            return genome_id
        except Exception as exc:
            logger.error("snapshot.restore_failed: %s", exc)
            return None

    def export_json(self, snapshot: SnapshotPayload) -> str:
        """Export snapshot as portable JSON string."""
        data = {
            "snapshot_id": str(snapshot.snapshot_id),
            "agent_id": str(snapshot.agent_id),
            "workspace_id": str(snapshot.workspace_id),
            "captured_at": snapshot.captured_at,
            "flow_version": snapshot.flow_version,
            "snapshot_format": snapshot.snapshot_format,
            "genome": snapshot.genome,
            "skills": snapshot.skills,
            "metacog_journal": snapshot.metacog_journal,
            "calibration_stats": snapshot.calibration_stats,
            "bandit_arms": snapshot.bandit_arms,
            "recent_traces": snapshot.recent_traces,
            "rl_episodes": snapshot.rl_episodes,
        }
        return json.dumps(data, indent=2, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> SnapshotPayload:
        """Import snapshot from JSON string."""
        data = json.loads(json_str)
        return SnapshotPayload(
            snapshot_id=UUID(data["snapshot_id"]),
            agent_id=UUID(data["agent_id"]),
            workspace_id=UUID(data["workspace_id"]),
            captured_at=data["captured_at"],
            genome=data.get("genome", {}),
            skills=data.get("skills", []),
            metacog_journal=data.get("metacog_journal", []),
            calibration_stats=data.get("calibration_stats", {}),
            bandit_arms=data.get("bandit_arms", []),
            recent_traces=data.get("recent_traces", []),
            rl_episodes=data.get("rl_episodes", []),
            flow_version=data.get("flow_version", "2.0.0"),
            snapshot_format=data.get("snapshot_format", 1),
        )
