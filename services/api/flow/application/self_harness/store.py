"""Pool-backed helpers for Self-Harness: golden split access + edit audit log."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from flow.application.self_harness.types import HarnessEdit


async def get_split_items(pool: Any, golden_set_id: UUID) -> tuple[list[dict], list[dict]]:
    """Return (held_in, held_out) item lists for a golden set.

    Rows with a NULL split are partitioned on the fly by the same stable hash the
    migration uses, so newly added items are assigned deterministically.
    """
    rows = await pool.fetch(
        """
        SELECT input_text, expected_output, scoring_criteria,
               COALESCE(
                   split,
                   CASE WHEN (hashtext(id::text)::bigint & 1) = 0 THEN 'held_in' ELSE 'held_out' END
               ) AS split
        FROM golden_items
        WHERE set_id = $1
        """,
        golden_set_id,
    )
    held_in, held_out = [], []
    for r in rows:
        item = {
            "input_text": r["input_text"],
            "expected_output": r["expected_output"],
            "scoring_criteria": r["scoring_criteria"],
        }
        (held_in if r["split"] == "held_in" else held_out).append(item)
    return held_in, held_out


async def log_edit(
    pool: Any,
    round_id: UUID,
    agent_id: UUID,
    workspace_id: UUID,
    edit: HarnessEdit,
    *,
    delta_in: float | None,
    delta_ho: float | None,
    accepted: bool,
) -> None:
    """Record one evaluated candidate edit (accepted or rejected)."""
    await pool.execute(
        """
        INSERT INTO self_harness_edits
            (id, round_id, agent_id, workspace_id, surface, mutation_type, target,
             payload, delta_in, delta_ho, accepted, rationale, source_pattern)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10, $11, $12, $13)
        """,
        uuid4(),
        round_id,
        agent_id,
        workspace_id,
        edit.surface,
        edit.mutation_type,
        edit.target,
        json.dumps(edit.payload),
        delta_in,
        delta_ho,
        accepted,
        edit.rationale,
        edit.source_pattern,
    )
