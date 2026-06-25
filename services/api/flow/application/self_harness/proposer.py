"""Stage 2 — Harness Proposal.

Translate a ranked EvidenceBundle into K mutually-distinct, minimal candidate
edits. Each edit targets one pattern and one declared surface; broad rewrites of
the control architecture are disallowed. The same model acts as proposer.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from flow.application.self_harness.types import CONFIG_SURFACES, EvidenceBundle, HarnessEdit

logger = logging.getLogger(__name__)

_MUTATION_TYPE = {
    "system_prompt": "prompt_rewrite",
    "loops": "loops_tune",
    "tools": "tool_toggle",
    "temperature": "temperature_sweep",
    "skill": "skill_mutate",
}

_LOOP_DEFAULTS = {
    "bandit_selection": True,
    "progress_guard": True,
    "feed_mistakes_forward": True,
    "max_tool_iters": 8,
    "max_retries": 2,
}

_PROPOSER_PROMPT = """\
You improve an AI agent's harness by proposing small, targeted edits. You are given
ranked failure patterns and the current editable surfaces. Propose up to {k} edits.

Rules:
- Each edit targets EXACTLY ONE failure pattern and ONE surface from: {surfaces}.
- Edits must be mutually distinct (different pattern/surface/mechanism), not reworded.
- Minimal: change only what is needed; never rewrite the whole control architecture.
- A pattern that is not addressable by these surfaces should be skipped, not forced.

Surface payloads:
- system_prompt: {{"system_prompt": "<full revised prompt, surgical changes>"}}
- loops:         target "loops:<key>", payload {{"value": <int|bool>}}
                 keys: max_tool_iters (int), max_retries (int), progress_guard (bool),
                 feed_mistakes_forward (bool)
- tools:         target "tool:<name>", payload {{"enabled": <bool>}}
- temperature:   payload {{"value": <float 0..1>}}

Return ONLY a JSON array:
[{{"surface": "...", "target": "...", "payload": {{...}},
   "rationale": "<one sentence>", "source_pattern": "<cause||mechanism>"}}]
"""


def _surfaces_snapshot(config: dict) -> str:
    loops = {**_LOOP_DEFAULTS, **(config.get("loops") or {})}
    llm_cfg = config.get("llm_config") or config.get("model") or {}
    prompt = str(config.get("system_prompt", ""))[:800]
    return (
        f"system_prompt (truncated): {prompt}\n"
        f"loops: {json.dumps(loops)}\n"
        f"tools: {json.dumps(config.get('tools') or {})}\n"
        f"temperature: {llm_cfg.get('temperature', 0.2)}"
    )


async def propose_edits(
    config: dict,
    bundle: EvidenceBundle,
    *,
    llm: Any = None,
    allowed_surfaces: tuple[str, ...] = CONFIG_SURFACES,
    k: int = 3,
) -> list[HarnessEdit]:
    """Generate up to ``k`` bounded HarnessEdits from the evidence bundle."""
    patterns = bundle.ranked()
    if not patterns or llm is None:
        return []

    patterns_desc = "\n".join(
        f"- [{p.signature}] cause={p.cause}; mechanism={p.mechanism}; suggested_surface={p.candidate_surface}; support={p.support}"
        for p in patterns[: max(k * 2, 6)]
    )

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        out = await llm.ainvoke(
            [
                SystemMessage(content=_PROPOSER_PROMPT.format(k=k, surfaces=", ".join(allowed_surfaces))),
                HumanMessage(content=f"Failure patterns (ranked):\n{patterns_desc}\n\nCurrent surfaces:\n{_surfaces_snapshot(config)}"),
            ]
        )
        raw = str(out.content).strip()
        if "```" in raw:
            raw = raw.split("```")[1].removeprefix("json").strip()
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
    except Exception as exc:
        logger.debug("proposer.generate_failed: %s", exc)
        return []

    edits: list[HarnessEdit] = []
    seen: set[tuple[str, str]] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        surface = str(item.get("surface", "")).strip()
        if surface not in allowed_surfaces:
            continue
        target = str(item.get("target", surface)).strip() or surface
        key = (surface, target)
        if key in seen:
            continue  # enforce distinctness
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        seen.add(key)
        edits.append(
            HarnessEdit(
                surface=surface,
                mutation_type=_MUTATION_TYPE.get(surface, "config_patch"),
                target=target,
                payload=payload,
                rationale=str(item.get("rationale", "")),
                source_pattern=str(item.get("source_pattern", "")),
            )
        )
        if len(edits) >= k:
            break
    return edits
