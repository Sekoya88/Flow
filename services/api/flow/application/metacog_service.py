"""MetaCognition Service — Phase 2.

Orchestrates metacognitive operations post-execution:
  1. Skill-level evaluation (which skills helped vs hurt)
  2. Mutation proposals when performance drops
  3. Metacognitive journal entries (queryable audit trail)
  4. Confidence calibration tracking

Replaces the simple grade-only reflector with a structured metacognitive system.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


@dataclass
class SkillScore:
    """Per-skill evaluation result."""

    skill_id: UUID
    skill_name: str
    contribution: float  # -1.0 to 1.0 — negative = hurt, positive = helped
    rationale: str = ""


@dataclass
class Mutation:
    """A proposed mutation to the agent genome."""

    mutation_type: str  # MutationType value
    target: str  # "system_prompt" | "skill:<name>" | "tool:<name>"
    description: str
    confidence: float  # 0.0–1.0
    proposed_change: str = ""  # diff or new content


@dataclass
class MetaCogEntry:
    """A single metacognitive journal entry."""

    execution_id: UUID | None
    grade: int  # 1–5
    prediction: str  # predicted next query/topic
    calibration_error: float  # |predicted_confidence - actual_grade/5|
    skill_scores: list[SkillScore] = field(default_factory=list)
    mutations_proposed: list[Mutation] = field(default_factory=list)
    reasoning: str = ""  # free-text self-reflection


class MetaCogService:
    """Orchestrates metacognitive operations post-execution."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def evaluate_skills(
        self,
        execution_id: UUID,
        matched_skills: list[dict],
        grade: int,
        user_text: str,
        answer: str,
        *,
        llm: Any = None,
    ) -> list[SkillScore]:
        """Evaluate each matched skill's contribution to the answer quality.

        Uses LLM to assess whether each skill helped or hurt, returning a
        contribution score from -1.0 (actively harmful) to 1.0 (critical help).
        """
        if not matched_skills or llm is None:
            return []

        skills_desc = "\n".join(f"- {s['name']} (v{s.get('version', '?')}): triggers={s.get('triggers', [])}" for s in matched_skills)

        prompt = f"""\
You are evaluating which skills helped vs hurt in this AI interaction.

User question: {user_text[:500]}
Answer quality grade: {grade}/5
Skills that were active:
{skills_desc}

For each skill, rate its contribution from -1.0 (actively harmful — caused errors or confusion)
to 1.0 (critical help — answer would be much worse without it).

Return ONLY valid JSON array:
[{{"name": "skill-name", "contribution": 0.7, "rationale": "one sentence"}}]
"""
        try:
            from langchain_core.messages import HumanMessage

            out = await llm.ainvoke([HumanMessage(content=prompt)])
            raw = str(out.content).strip()
            if "```" in raw:
                raw = raw.split("```")[1].removeprefix("json").strip()
            data = json.loads(raw)
            if not isinstance(data, list):
                return []

            scores = []
            for item in data:
                name = item.get("name", "")
                skill_match = next((s for s in matched_skills if s["name"] == name), None)
                if skill_match:
                    scores.append(
                        SkillScore(
                            skill_id=UUID(skill_match["skill_id"]),
                            skill_name=name,
                            contribution=max(-1.0, min(1.0, float(item.get("contribution", 0)))),
                            rationale=str(item.get("rationale", "")),
                        )
                    )
            return scores
        except Exception as exc:
            logger.debug("metacog.evaluate_skills failed: %s", exc)
            return []

    async def propose_mutations(
        self,
        agent_id: UUID,
        workspace_id: UUID,
        grade: int,
        skill_scores: list[SkillScore],
        user_text: str,
        answer: str,
        *,
        llm: Any = None,
    ) -> list[Mutation]:
        """Generate mutation candidates when performance drops (grade <= 2).

        Returns proposed mutations sorted by confidence DESC.
        """
        if grade > 2 or llm is None:
            return []

        # Identify worst-performing skills
        bad_skills = [s for s in skill_scores if s.contribution < 0]
        bad_skills_desc = (
            "\n".join(f"- {s.skill_name}: contribution={s.contribution:.2f}, {s.rationale}" for s in bad_skills) or "(no skills were harmful)"
        )

        prompt = f"""\
An AI agent scored {grade}/5 on this interaction. Propose 1-3 targeted mutations to improve it.

User question: {user_text[:300]}
Answer excerpt: {answer[:500]}
Harmful skills: {bad_skills_desc}

Mutation types: prompt_rewrite, skill_mutate, tool_toggle, temperature_sweep
Return ONLY valid JSON array:
[{{"mutation_type": "...", "target": "system_prompt|skill:<name>|tool:<name>", "description": "what to change", "confidence": 0.75}}]
"""
        try:
            from langchain_core.messages import HumanMessage

            out = await llm.ainvoke([HumanMessage(content=prompt)])
            raw = str(out.content).strip()
            if "```" in raw:
                raw = raw.split("```")[1].removeprefix("json").strip()
            data = json.loads(raw)
            if not isinstance(data, list):
                return []

            mutations = []
            for item in data:
                mutations.append(
                    Mutation(
                        mutation_type=str(item.get("mutation_type", "prompt_rewrite")),
                        target=str(item.get("target", "system_prompt")),
                        description=str(item.get("description", "")),
                        confidence=max(0.0, min(1.0, float(item.get("confidence", 0.5)))),
                    )
                )
            mutations.sort(key=lambda m: m.confidence, reverse=True)
            return mutations[:3]
        except Exception as exc:
            logger.debug("metacog.propose_mutations failed: %s", exc)
            return []

    async def file_mutation_proposal(
        self,
        agent_id: UUID,
        workspace_id: UUID,
        mutations: list[Mutation],
        *,
        grade: int,
        execution_id: UUID | None = None,
        min_confidence: float = 0.6,
        rate_limit_hours: int = 24,
    ) -> UUID | None:
        """Surface high-confidence metacog mutations as a reviewable proposal.

        Closes the metacog → proposal loop: mutations used to die in the journal,
        invisible. Now the strong ones become a pending proposal a human can
        review (and, on approval, the existing proposals flow can act on).

        Rate-limited: skips if a metacog proposal for this agent is already
        pending or was filed within ``rate_limit_hours``. Returns the proposal id,
        or None if nothing was filed.
        """
        strong = [m for m in mutations if m.confidence >= min_confidence]
        if not strong:
            return None

        title_marker = f"[Metacog] Agent {str(agent_id)[:8]} — "
        try:
            recent = await self._pool.fetchval(
                """
                SELECT count(*) FROM proposals
                WHERE workspace_id = $1
                  AND title LIKE $2
                  AND (status = 'pending' OR created_at > now() - ($3 || ' hours')::interval)
                """,
                workspace_id,
                title_marker + "%",
                str(rate_limit_hours),
            )
            if recent and int(recent) > 0:
                return None

            owner = await self._pool.fetchrow(
                """SELECT user_id FROM workspace_members
                   WHERE workspace_id = $1
                   ORDER BY (role = 'owner') DESC LIMIT 1""",
                workspace_id,
            )
            if not owner:
                return None

            body = json.dumps(
                {
                    "kind": "metacog_mutation",
                    "agent_id": str(agent_id),
                    "execution_id": str(execution_id) if execution_id else None,
                    "grade": grade,
                    "mutations": [
                        {
                            "mutation_type": m.mutation_type,
                            "target": m.target,
                            "description": m.description,
                            "confidence": m.confidence,
                        }
                        for m in strong
                    ],
                    "summary": (
                        f"Metacognition graded a run {grade}/5 and proposed "
                        f"{len(strong)} high-confidence improvement(s). Review before applying."
                    ),
                }
            )
            proposal_id = uuid4()
            await self._pool.execute(
                """INSERT INTO proposals (id, workspace_id, user_id, title, body, status)
                   VALUES ($1, $2, $3, $4, $5, 'pending')""",
                proposal_id,
                workspace_id,
                owner["user_id"],
                title_marker + strong[0].description[:60],
                body,
            )
            return proposal_id
        except Exception as exc:
            logger.debug("metacog.file_mutation_proposal failed: %s", exc)
            return None

    async def update_journal(
        self,
        agent_id: UUID,
        workspace_id: UUID,
        entry: MetaCogEntry,
    ) -> UUID:
        """Append to metacognitive journal. Returns the journal entry ID."""
        entry_id = uuid4()
        try:
            skill_scores_json = [
                {
                    "skill_id": str(s.skill_id),
                    "skill_name": s.skill_name,
                    "contribution": s.contribution,
                    "rationale": s.rationale,
                }
                for s in entry.skill_scores
            ]
            mutations_json = [
                {
                    "mutation_type": m.mutation_type,
                    "target": m.target,
                    "description": m.description,
                    "confidence": m.confidence,
                }
                for m in entry.mutations_proposed
            ]
            await self._pool.execute(
                """
                INSERT INTO metacog_journal
                    (id, agent_id, workspace_id, execution_id, grade, prediction,
                     calibration_error, skill_scores, mutations_proposed, reasoning)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10)
                """,
                entry_id,
                agent_id,
                workspace_id,
                entry.execution_id,
                entry.grade,
                entry.prediction,
                entry.calibration_error,
                json.dumps(skill_scores_json),
                json.dumps(mutations_json),
                entry.reasoning,
            )
        except Exception as exc:
            logger.warning("metacog.journal_write_failed: %s", exc)
        return entry_id

    async def calibrate_confidence(
        self,
        agent_id: UUID,
        workspace_id: UUID,
        predicted_confidence: float,
        actual_grade: int,
    ) -> float:
        """Compute and return calibration error.

        calibration_error = |predicted_confidence - actual_grade/5|
        Over time, a well-calibrated agent should have low average calibration error.
        """
        normalized_grade = actual_grade / 5.0
        error = abs(predicted_confidence - normalized_grade)
        return round(error, 4)

    async def get_journal(
        self,
        agent_id: UUID,
        workspace_id: UUID,
        limit: int = 20,
    ) -> list[dict]:
        """Fetch recent metacognitive journal entries."""
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
                limit,
            )
            return [dict(r) for r in rows]
        except Exception:
            return []

    async def get_calibration_stats(
        self,
        agent_id: UUID,
        workspace_id: UUID,
    ) -> dict[str, float]:
        """Compute aggregate calibration statistics."""
        try:
            row = await self._pool.fetchrow(
                """
                SELECT
                    AVG(calibration_error) AS avg_error,
                    STDDEV(calibration_error) AS std_error,
                    COUNT(*) AS total_entries,
                    AVG(grade) AS avg_grade
                FROM metacog_journal
                WHERE agent_id = $1 AND workspace_id = $2
                  AND created_at > now() - interval '30 days'
                """,
                agent_id,
                workspace_id,
            )
            if row is None:
                return {"avg_error": 0.0, "std_error": 0.0, "total_entries": 0, "avg_grade": 0.0}
            return {
                "avg_error": float(row["avg_error"] or 0.0),
                "std_error": float(row["std_error"] or 0.0),
                "total_entries": int(row["total_entries"] or 0),
                "avg_grade": float(row["avg_grade"] or 0.0),
            }
        except Exception:
            return {"avg_error": 0.0, "std_error": 0.0, "total_entries": 0, "avg_grade": 0.0}
