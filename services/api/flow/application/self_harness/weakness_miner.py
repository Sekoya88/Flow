"""Stage 1 — Weakness Mining.

Convert verifier-grounded failures (golden_results below threshold on the held-in
split) into a ranked EvidenceBundle of recurring failure *patterns*, rather than
isolated mistakes. Each failure is attributed to a (cause, mechanism) signature by
the same model; failures are clustered by exact signature and ranked by
support × actionability. Non-addressable clusters are excluded, not patched.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from flow.application.self_harness.types import ALL_SURFACES, EvidenceBundle, FailurePattern

logger = logging.getLogger(__name__)

PASS_THRESHOLD = 0.7

_ATTRIBUTION_PROMPT = """\
You are diagnosing why an AI agent failed a set of graded tasks. For EACH failure,
attribute it to a reusable failure mechanism — not a one-off symptom.

Return ONLY a JSON array, one object per failure, aligned to the input order:
[{{"cause": "<terminal reason the grader rejected it, short>",
   "mechanism": "<reusable agent behavior that caused it, short>",
   "surface": "system_prompt|loops|tools|temperature|skill|none",
   "actionability": <0.0-1.0>}}]

"surface" is the harness surface most likely to fix the mechanism with a narrow edit;
use "none" if the failure reflects task difficulty or a model capability limit rather
than a missing execution rule. "loops" = runtime control (max tool iterations, loop
breaking, retry discipline). Keep cause/mechanism as short canonical phrases so
similar failures collapse to the same wording.
"""


async def _fetch_held_in_failures(pool: Any, agent_id: UUID, limit: int) -> list[dict]:
    rows = await pool.fetch(
        """
        SELECT gi.input_text, gi.expected_output, gr.actual_output, gr.score, gr.grading_rationale
        FROM golden_results gr
        JOIN golden_items gi ON gi.id = gr.item_id
        WHERE gr.agent_id = $1
          AND gr.score IS NOT NULL AND gr.score < $2
          AND COALESCE(
                gi.split,
                CASE WHEN (hashtext(gi.id::text)::bigint & 1) = 0 THEN 'held_in' ELSE 'held_out' END
              ) = 'held_in'
        ORDER BY gr.created_at DESC
        LIMIT $3
        """,
        agent_id,
        PASS_THRESHOLD,
        limit,
    )
    return [dict(r) for r in rows]


async def mine_weaknesses(
    pool: Any,
    agent_id: UUID,
    *,
    llm: Any = None,
    max_failures: int = 20,
) -> EvidenceBundle:
    """Cluster recent held-in failures into a ranked EvidenceBundle.

    Best-effort: returns an empty bundle when there are no failures or no LLM.
    """
    if llm is None:
        return EvidenceBundle()

    failures = await _fetch_held_in_failures(pool, agent_id, max_failures)
    if not failures:
        return EvidenceBundle()

    items_desc = "\n".join(
        f"[{i}] Q: {f.get('input_text', '')[:300]}\n"
        f"    expected: {str(f.get('expected_output', ''))[:200]}\n"
        f"    actual: {str(f.get('actual_output', ''))[:200]}\n"
        f"    grader: {str(f.get('grading_rationale', ''))[:200]}"
        for i, f in enumerate(failures)
    )

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        out = await llm.ainvoke(
            [
                SystemMessage(content=_ATTRIBUTION_PROMPT),
                HumanMessage(content=f"Failures:\n{items_desc}"),
            ]
        )
        raw = str(out.content).strip()
        if "```" in raw:
            raw = raw.split("```")[1].removeprefix("json").strip()
        attributions = json.loads(raw)
        if not isinstance(attributions, list):
            return EvidenceBundle()
    except Exception as exc:
        logger.debug("weakness_miner.attribution_failed: %s", exc)
        return EvidenceBundle()

    # Cluster by exact (cause, mechanism) signature, excluding non-addressable ones.
    clusters: dict[str, dict] = {}
    for i, attr in enumerate(attributions):
        if not isinstance(attr, dict):
            continue
        surface = str(attr.get("surface", "none")).strip()
        if surface == "none" or surface not in ALL_SURFACES:
            continue  # not addressable by a harness edit — excluded, not forced
        cause = str(attr.get("cause", "")).strip().lower()
        mechanism = str(attr.get("mechanism", "")).strip().lower()
        if not cause or not mechanism:
            continue
        sig = f"{cause}||{mechanism}"
        c = clusters.setdefault(
            sig,
            {"cause": cause, "mechanism": mechanism, "surface": surface, "inputs": [], "actionability": []},
        )
        c["actionability"].append(max(0.0, min(1.0, float(attr.get("actionability", 0.5)))))
        if i < len(failures):
            c["inputs"].append(str(failures[i].get("input_text", ""))[:300])

    patterns = [
        FailurePattern(
            cause=c["cause"],
            mechanism=c["mechanism"],
            support=len(c["actionability"]),
            candidate_surface=c["surface"],
            representative_inputs=c["inputs"][:3],
            actionability=sum(c["actionability"]) / len(c["actionability"]),
        )
        for c in clusters.values()
    ]
    return EvidenceBundle(patterns=patterns)
