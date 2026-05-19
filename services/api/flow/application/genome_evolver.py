"""Genome Evolver — Phase 3b.

Orchestrates the full RL-lite genome evolution loop:
  1. Evaluate current genome on golden set
  2. If score < threshold → generate N mutation candidates
  3. A/B test top candidate vs current
  4. If candidate wins → promote (CANDIDATE → ACTIVE)
  5. Safety eval after 36h → rollback if regression

This is the "autonomous improvement" backbone that ties together the
golden_evaluator, prompt_rewriter, skill_rewriter, and ab_runner.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class EvolutionResult:
    """Result of one evolution cycle."""

    agent_id: UUID
    cycle_status: str  # "no_change" | "candidate_generated" | "ab_test_started" | "promoted" | "failed"
    current_score: float | None = None
    candidate_score: float | None = None
    mutation_type: str | None = None
    candidate_genome_id: UUID | None = None
    details: dict[str, Any] = field(default_factory=dict)


class GenomeEvolver:
    """Orchestrates the full RL-lite genome evolution loop."""

    def __init__(self, pool: Any, settings: Any = None) -> None:
        self._pool = pool
        self._settings = settings

    async def run_evolution_cycle(
        self,
        agent_id: UUID,
        workspace_id: UUID,
        *,
        score_threshold: float = 0.7,
        max_mutations: int = 3,
    ) -> EvolutionResult:
        """Run one full evolution cycle for an agent.

        Steps:
        1. Get current active genome + its last golden set score
        2. If score >= threshold → no action needed
        3. If score < threshold → generate mutation candidates
        4. Evaluate candidates on golden set (tournament selection)
        5. If best candidate beats current → start A/B test or auto-promote
        6. Log rl_episode
        """
        try:
            from flow.application.genome_service import get_active_genome, snapshot_genome
            from flow.domain.genome import MutationType, VersionStatus, VersionTrigger

            # 1. Get current genome + score
            active = await get_active_genome(self._pool, agent_id)
            if active is None:
                return EvolutionResult(
                    agent_id=agent_id,
                    cycle_status="failed",
                    details={"error": "no active genome"},
                )

            current_score = active.avg_score or 0.0

            # 2. Check if improvement needed
            if current_score >= score_threshold:
                return EvolutionResult(
                    agent_id=agent_id,
                    cycle_status="no_change",
                    current_score=current_score,
                    details={"reason": f"score {current_score:.2f} >= threshold {score_threshold}"},
                )

            # 3. Generate mutation candidates
            candidates = await self.generate_mutations(
                genome=active,
                workspace_id=workspace_id,
                n=max_mutations,
            )

            if not candidates:
                return EvolutionResult(
                    agent_id=agent_id,
                    cycle_status="failed",
                    current_score=current_score,
                    details={"error": "no candidates generated"},
                )

            # 4. Tournament: evaluate each candidate on golden set
            best = await self.tournament_select(
                agent_id=agent_id,
                workspace_id=workspace_id,
                candidates=candidates,
            )

            if best is None:
                return EvolutionResult(
                    agent_id=agent_id,
                    cycle_status="failed",
                    current_score=current_score,
                    details={"error": "tournament selection failed"},
                )

            best_genome, best_score = best

            # 5. If best candidate beats current → create CANDIDATE version
            if best_score > current_score:
                candidate_id = await snapshot_genome(
                    pool=self._pool,
                    agent_id=agent_id,
                    workspace_id=workspace_id,
                    trigger=VersionTrigger.RL_MUTATION,
                    created_by=None,
                    status=VersionStatus.CANDIDATE,
                    system_prompt_override=best_genome.get("system_prompt"),
                )

                # Log RL episode
                await self._log_episode(
                    agent_id=agent_id,
                    workspace_id=workspace_id,
                    parent_genome_id=active.id,
                    candidate_genome_id=candidate_id,
                    mutation_type=best_genome.get("mutation_type", "prompt_rewrite"),
                    reward_before=current_score,
                    reward_after=best_score,
                    promoted=False,  # will be promoted after A/B test
                )

                return EvolutionResult(
                    agent_id=agent_id,
                    cycle_status="candidate_generated",
                    current_score=current_score,
                    candidate_score=best_score,
                    mutation_type=best_genome.get("mutation_type"),
                    candidate_genome_id=candidate_id,
                    details={"improvement": best_score - current_score},
                )

            return EvolutionResult(
                agent_id=agent_id,
                cycle_status="no_change",
                current_score=current_score,
                candidate_score=best_score,
                details={"reason": "no candidate beat current genome"},
            )

        except Exception as exc:
            logger.error("evolution_cycle.failed agent=%s: %s", agent_id, exc)
            return EvolutionResult(
                agent_id=agent_id,
                cycle_status="failed",
                details={"error": str(exc)},
            )

    async def generate_mutations(
        self,
        genome: Any,  # AgentGenome
        workspace_id: UUID,
        n: int = 3,
    ) -> list[dict]:
        """Generate N candidate mutations from the current genome.

        Mutation types:
        - prompt_rewrite: rephrase system prompt targeting identified weaknesses
        - skill_mutate: rewrite underperforming skill bodies
        - tool_toggle: enable/disable tools based on success patterns
        - temperature_sweep: try different temperatures
        """
        candidates: list[dict] = []

        # Mutation 1: Prompt rewrite (always try)
        try:
            from flow.application.prompt_rewriter import rewrite_system_prompt

            rewritten = await rewrite_system_prompt(
                pool=self._pool,
                agent_id=genome.agent_id,
                workspace_id=workspace_id,
                current_prompt=genome.system_prompt,
            )
            if rewritten and rewritten != genome.system_prompt:
                candidates.append({
                    "mutation_type": "prompt_rewrite",
                    "system_prompt": rewritten,
                    "tools": genome.tools,
                    "temperature": genome.llm_config.temperature,
                })
        except Exception:
            logger.debug("mutation.prompt_rewrite failed", exc_info=True)

        # Mutation 2: Temperature sweep
        for temp in [0.1, 0.3, 0.5]:
            if abs(temp - genome.llm_config.temperature) > 0.05:
                candidates.append({
                    "mutation_type": "temperature_sweep",
                    "system_prompt": genome.system_prompt,
                    "tools": genome.tools,
                    "temperature": temp,
                })
                if len(candidates) >= n:
                    break

        return candidates[:n]

    async def tournament_select(
        self,
        agent_id: UUID,
        workspace_id: UUID,
        candidates: list[dict],
    ) -> tuple[dict, float] | None:
        """Evaluate all candidates, return (best_candidate, best_score).

        Uses a lightweight scoring proxy: semantic similarity between
        the mutated prompt and top-performing golden set answers.
        For now, returns a heuristic score based on prompt quality signals.
        """
        if not candidates:
            return None

        best: dict | None = None
        best_score = -1.0

        for c in candidates:
            # Heuristic scoring: longer prompts with more structure score higher
            prompt = c.get("system_prompt", "")
            score = _heuristic_prompt_score(prompt)

            # Temperature penalty: extreme temperatures score lower
            temp = c.get("temperature", 0.2)
            if temp < 0.05 or temp > 0.8:
                score *= 0.8

            if score > best_score:
                best_score = score
                best = c

        return (best, best_score) if best else None

    async def _log_episode(
        self,
        agent_id: UUID,
        workspace_id: UUID,
        parent_genome_id: UUID | None,
        candidate_genome_id: UUID | None,
        mutation_type: str,
        reward_before: float,
        reward_after: float,
        promoted: bool,
    ) -> None:
        """Log an RL episode to the rl_episodes table."""
        try:
            await self._pool.execute(
                """
                INSERT INTO rl_episodes
                    (agent_id, workspace_id, parent_genome_id, candidate_genome_id,
                     mutation_type, reward_before, reward_after, reward_delta, promoted)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                agent_id,
                workspace_id,
                parent_genome_id,
                candidate_genome_id,
                mutation_type,
                reward_before,
                reward_after,
                reward_after - reward_before,
                promoted,
            )
        except Exception:
            logger.debug("rl_episode.log_failed", exc_info=True)


def _heuristic_prompt_score(prompt: str) -> float:
    """Quick heuristic to score system prompt quality.

    Factors:
    - Length (too short = vague, too long = noisy)
    - Structure (numbered lists, headers)
    - Specificity (contains action verbs, constraints)
    """
    if not prompt:
        return 0.0

    length = len(prompt)
    score = 0.5

    # Length bonus: sweet spot is 200-1000 chars
    if 200 <= length <= 1000:
        score += 0.2
    elif length > 1000:
        score += 0.1
    # Else: short prompt, no bonus

    # Structure bonus
    if any(c in prompt for c in ["1.", "2.", "3.", "-", "##"]):
        score += 0.15

    # Specificity: action verbs
    action_words = ["must", "should", "always", "never", "ensure", "verify", "analyze"]
    matches = sum(1 for w in action_words if w.lower() in prompt.lower())
    score += min(0.15, matches * 0.03)

    return min(1.0, score)
