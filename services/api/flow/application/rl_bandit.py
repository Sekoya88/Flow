"""Thompson Sampling Bandit for Skill Selection — Phase 3a (RL-lite).

Each skill is a "bandit arm" with a Beta(alpha, beta) prior.
On success (grade >= 4): alpha += 1
On failure (grade <= 2): beta += 1
Selection: sample from Beta distribution, pick top-K skills.

This replaces the trigger-based skill matching with an explore/exploit
strategy that learns which skills are most valuable for each agent.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class ArmStats:
    """Statistics for a single bandit arm (skill)."""

    skill_id: UUID
    skill_name: str
    alpha: float  # successes + prior
    beta: float  # failures + prior
    total_pulls: int
    total_reward: float
    mean: float  # alpha / (alpha + beta)


class SkillBandit:
    """Thompson Sampling bandit for skill selection.

    Maintains Beta(alpha, beta) posteriors per skill in the DB.
    Uses Thompson Sampling to balance exploration (trying underused skills)
    and exploitation (using high-performing skills).
    """

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def select_skills(
        self,
        agent_id: UUID,
        available_skill_ids: list[UUID],
        k: int = 3,
    ) -> list[UUID]:
        """Select k skills via Thompson Sampling.

        For each available skill, sample from its Beta(alpha, beta) posterior.
        Return the top-k by sampled value.
        Falls back to random selection if no arm stats exist.
        """
        if not available_skill_ids:
            return []

        k = min(k, len(available_skill_ids))

        arms = await self._get_or_create_arms(agent_id, available_skill_ids)

        # Thompson Sampling: sample from each arm's Beta distribution
        sampled: list[tuple[UUID, float]] = []
        for skill_id in available_skill_ids:
            arm = arms.get(skill_id)
            if arm is None:
                # New arm — uninformative prior Beta(1, 1) = uniform
                sample = random.betavariate(1.0, 1.0)
            else:
                sample = random.betavariate(arm.alpha, arm.beta)
            sampled.append((skill_id, sample))

        # Sort by sampled value DESC, take top-k
        sampled.sort(key=lambda x: x[1], reverse=True)
        selected = [s[0] for s in sampled[:k]]

        logger.debug(
            "bandit.select",
            extra={
                "agent_id": str(agent_id),
                "selected": [str(s) for s in selected],
                "samples": {str(s[0]): round(s[1], 3) for s in sampled},
            },
        )
        return selected

    async def update(
        self,
        agent_id: UUID,
        skill_id: UUID,
        reward: float,
    ) -> None:
        """Update Beta distribution for a skill based on reward signal.

        reward > 0.6 → success (alpha += reward)
        reward < 0.4 → failure (beta += 1 - reward)
        0.4 <= reward <= 0.6 → neutral (small update to both)
        """
        if reward > 0.6:
            alpha_inc = reward
            beta_inc = 0.0
        elif reward < 0.4:
            alpha_inc = 0.0
            beta_inc = 1.0 - reward
        else:
            # Neutral — slight exploration nudge
            alpha_inc = 0.1
            beta_inc = 0.1

        try:
            await self._pool.execute(
                """
                INSERT INTO skill_bandit_arms (skill_id, agent_id, alpha, beta, total_pulls, total_reward)
                VALUES ($1, $2, $3, $4, 1, $5)
                ON CONFLICT (skill_id, agent_id) DO UPDATE SET
                    alpha = skill_bandit_arms.alpha + $3 - 1.0,
                    beta = skill_bandit_arms.beta + $4 - 1.0,
                    total_pulls = skill_bandit_arms.total_pulls + 1,
                    total_reward = skill_bandit_arms.total_reward + $5,
                    updated_at = now()
                """,
                skill_id,
                agent_id,
                1.0 + alpha_inc,  # prior + increment
                1.0 + beta_inc,   # prior + increment
                reward,
            )
        except Exception as exc:
            logger.warning("bandit.update_failed: %s", exc)

    async def batch_update(
        self,
        agent_id: UUID,
        skill_rewards: list[tuple[UUID, float]],
    ) -> None:
        """Update multiple skill arms at once."""
        for skill_id, reward in skill_rewards:
            await self.update(agent_id, skill_id, reward)

    async def get_arm_stats(self, agent_id: UUID) -> dict[UUID, ArmStats]:
        """Get current arm statistics for all skills of an agent."""
        try:
            rows = await self._pool.fetch(
                """
                SELECT ba.skill_id, ba.alpha, ba.beta, ba.total_pulls, ba.total_reward,
                       COALESCE(s.name, 'unknown') AS skill_name
                FROM skill_bandit_arms ba
                LEFT JOIN agent_skills s ON s.id = ba.skill_id
                WHERE ba.agent_id = $1
                ORDER BY ba.alpha / (ba.alpha + ba.beta) DESC
                """,
                agent_id,
            )
            result = {}
            for r in rows:
                sid = r["skill_id"]
                alpha = float(r["alpha"])
                beta = float(r["beta"])
                result[sid] = ArmStats(
                    skill_id=sid,
                    skill_name=r["skill_name"],
                    alpha=alpha,
                    beta=beta,
                    total_pulls=int(r["total_pulls"]),
                    total_reward=float(r["total_reward"]),
                    mean=alpha / (alpha + beta) if (alpha + beta) > 0 else 0.5,
                )
            return result
        except Exception:
            return {}

    async def _get_or_create_arms(
        self,
        agent_id: UUID,
        skill_ids: list[UUID],
    ) -> dict[UUID, ArmStats]:
        """Ensure all skill_ids have arm entries, return current stats."""
        existing = await self.get_arm_stats(agent_id)

        # Create missing arms with uninformative prior Beta(1, 1)
        missing = [sid for sid in skill_ids if sid not in existing]
        if missing:
            try:
                for sid in missing:
                    await self._pool.execute(
                        """
                        INSERT INTO skill_bandit_arms (skill_id, agent_id, alpha, beta, total_pulls, total_reward)
                        VALUES ($1, $2, 1.0, 1.0, 0, 0.0)
                        ON CONFLICT (skill_id, agent_id) DO NOTHING
                        """,
                        sid,
                        agent_id,
                    )
                # Re-fetch to include new arms
                existing = await self.get_arm_stats(agent_id)
            except Exception:
                pass

        return existing

    async def decay_arms(self, agent_id: UUID, decay_factor: float = 0.99) -> int:
        """Apply temporal decay to all arms (prevents stale priors).

        Pulls alpha and beta closer to 1.0 (uninformative prior) over time.
        Called by a daily cron job.
        """
        try:
            result = await self._pool.execute(
                """
                UPDATE skill_bandit_arms
                SET alpha = 1.0 + (alpha - 1.0) * $2,
                    beta = 1.0 + (beta - 1.0) * $2,
                    updated_at = now()
                WHERE agent_id = $1
                  AND (alpha > 1.01 OR beta > 1.01)
                """,
                agent_id,
                decay_factor,
            )
            # Extract count from "UPDATE N" string
            count = int(result.split()[-1]) if isinstance(result, str) else 0
            return count
        except Exception:
            return 0
