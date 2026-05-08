"""A/B test runner for comparing two agent genome versions on a golden set."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import asyncpg
from openai import AsyncOpenAI

from flow.application.golden_evaluator import judge_single

logger = logging.getLogger(__name__)

SIGNIFICANCE_THRESHOLD = 0.05


@dataclass
class VersionScore:
    version_id: UUID
    version_label: str
    avg_score: float
    pass_rate: float
    item_count: int
    per_item: list[dict] = field(default_factory=list)


@dataclass
class ABTestSummary:
    test_id: UUID
    golden_set_id: UUID
    version_a: VersionScore
    version_b: VersionScore
    winner_version_id: UUID | None
    delta: float
    significant: bool


class ABTestRunner:
    def __init__(self, pool: asyncpg.Pool, client: AsyncOpenAI | None = None) -> None:
        self._pool = pool
        self._client = client or AsyncOpenAI()

    async def run(
        self,
        test_id: UUID,
        golden_set_id: UUID,
        version_a_id: UUID,
        version_b_id: UUID,
        agent_id: UUID,
    ) -> ABTestSummary:
        """Score both versions, compute winner, persist results, return summary."""
        # Fetch version labels
        rows = await self._pool.fetch(
            "SELECT id, version_label FROM agent_versions WHERE id = ANY($1::uuid[])",
            [version_a_id, version_b_id],
        )
        labels: dict[UUID, str] = {r["id"]: r["version_label"] for r in rows}

        label_a = labels.get(version_a_id, str(version_a_id))
        label_b = labels.get(version_b_id, str(version_b_id))

        score_a = await self._score_version(
            golden_set_id=golden_set_id,
            version_id=version_a_id,
            agent_id=agent_id,
            version_label=label_a,
            test_id=test_id,
            ab_label="A",
        )
        score_b = await self._score_version(
            golden_set_id=golden_set_id,
            version_id=version_b_id,
            agent_id=agent_id,
            version_label=label_b,
            test_id=test_id,
            ab_label="B",
        )

        delta = score_b.avg_score - score_a.avg_score
        significant = abs(delta) >= SIGNIFICANCE_THRESHOLD
        winner: UUID | None = None
        if significant:
            winner = version_b_id if delta > 0 else version_a_id

        await self._pool.execute(
            "UPDATE ab_tests SET status = 'completed', version_a_id = $1, version_b_id = $2 "
            "WHERE id = $3",
            version_a_id, version_b_id, test_id,
        )

        logger.info(
            "ab_test.completed",
            extra={
                "test_id": str(test_id),
                "delta": round(delta, 4),
                "significant": significant,
                "winner": str(winner) if winner else None,
            },
        )

        return ABTestSummary(
            test_id=test_id,
            golden_set_id=golden_set_id,
            version_a=score_a,
            version_b=score_b,
            winner_version_id=winner,
            delta=delta,
            significant=significant,
        )

    async def _score_version(
        self,
        golden_set_id: UUID,
        version_id: UUID,
        agent_id: UUID,
        version_label: str,
        test_id: UUID,
        ab_label: str,
    ) -> VersionScore:
        """Judge all golden results for this version, insert ab_test_results rows."""
        items = await self._pool.fetch(
            """
            SELECT gr.actual_output, gi.input_text, gi.expected_output,
                   gi.scoring_criteria, gi.id AS item_id
            FROM golden_results gr
            JOIN golden_items gi ON gi.id = gr.item_id
            WHERE gi.set_id = $1
              AND gr.agent_id = $2
              AND gr.agent_version_label = $3
              AND gr.actual_output IS NOT NULL
            """,
            golden_set_id, agent_id, version_label,
        )

        scores: list[float] = []
        per_item: list[dict[str, Any]] = []

        for item in items:
            judgment = await judge_single(
                input_text=item["input_text"],
                expected_output=item["expected_output"],
                actual_output=item["actual_output"],
                scoring_criteria=item["scoring_criteria"],
                client=self._client,
            )
            score = judgment["score"]
            scores.append(score)
            per_item.append({
                "item_id": str(item["item_id"]),
                "score": score,
                "rationale": judgment["rationale"],
            })

            await self._pool.execute(
                """
                INSERT INTO ab_test_results
                    (id, test_id, golden_item_id, agent_label, score,
                     actual_output, grading_rationale)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                uuid4(), test_id, item["item_id"], ab_label,
                score, item["actual_output"], judgment["rationale"],
            )

        item_count = len(items)
        avg_score = sum(scores) / len(scores) if scores else 0.0
        pass_rate = len([s for s in scores if s >= 0.7]) / len(scores) if scores else 0.0

        return VersionScore(
            version_id=version_id,
            version_label=version_label,
            avg_score=avg_score,
            pass_rate=pass_rate,
            item_count=item_count,
            per_item=per_item,
        )
