"""Prompt Rewriter Agent — the core of the self-improvement feedback loop.

Given the current system prompt + failed golden-set items (with actual outputs,
expected outputs, and judge rationales), generates an **improved system prompt**
that addresses the specific failures.

This is the missing piece that turns static proposals into actionable genome
candidates with concrete prompt changes.

Design principles (inspired by LangChain deep-agent patterns):
  1. Structured analysis of failures → root-cause identification
  2. Targeted prompt mutations (not wholesale rewrites)
  3. Changelog generation for human review
  4. Idempotent: same inputs → deterministically similar outputs
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


@dataclass
class FailedItem:
    """A single golden-set item that the agent failed."""

    input_text: str
    expected_output: str
    actual_output: str
    score: float
    rationale: str


@dataclass
class RewriteResult:
    """Output of the prompt rewriter."""

    original_prompt: str
    improved_prompt: str
    changelog: list[str]  # human-readable list of changes made
    failure_analysis: str  # structured analysis of what went wrong
    confidence: float  # 0.0–1.0 — how confident the rewriter is
    metadata: dict[str, Any] = field(default_factory=dict)


_REWRITER_SYSTEM = """\
You are an expert AI prompt engineer specializing in iterative improvement.

Your task: Given a system prompt and a set of test cases where the AI failed,
produce an IMPROVED system prompt that fixes the failures while preserving
existing strengths.

## Rules
1. **Surgical edits**: Make targeted changes, not wholesale rewrites.
   Keep the original structure and voice.
2. **Root-cause first**: Analyze WHY each failure happened before proposing fixes.
3. **No regressions**: Your changes must not break items that were passing.
4. **Specific instructions**: Add concrete behavioral rules, not vague guidance.
5. **Format preservation**: If the original prompt uses a specific format
   (XML, markdown, JSON output instructions), preserve that format.

## Output Format
Return ONLY valid JSON in this exact format:
{
  "failure_analysis": "Brief root-cause analysis of the failures (2-4 sentences)",
  "changelog": ["Change 1: ...", "Change 2: ...", ...],
  "improved_prompt": "The full improved system prompt",
  "confidence": 0.85
}
"""


async def rewrite_prompt(
    current_prompt: str,
    failed_items: list[FailedItem],
    *,
    max_failures: int = 5,
    client: AsyncOpenAI | None = None,
    openai_api_key: str | None = None,
) -> RewriteResult:
    """Analyze failures and generate an improved system prompt.

    Args:
        current_prompt: The agent's current system prompt.
        failed_items: Items that scored below the pass threshold.
        max_failures: Max number of failures to include (to stay within context).
        client: Optional pre-configured OpenAI client.
        openai_api_key: API key fallback.

    Returns:
        RewriteResult with the improved prompt and changelog.
    """
    if client is None:
        api_key = openai_api_key or os.environ.get("FLOW_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        client = AsyncOpenAI(api_key=api_key)

    # Sort by worst score first, take top N
    sorted_failures = sorted(failed_items, key=lambda x: x.score)[:max_failures]

    failures_text = "\n\n".join(
        f"--- FAILURE {i + 1} (score: {f.score:.2f}) ---\n"
        f"Input: {f.input_text[:500]}\n"
        f"Expected: {f.expected_output[:500]}\n"
        f"Actual: {f.actual_output[:500]}\n"
        f"Judge rationale: {f.rationale}"
        for i, f in enumerate(sorted_failures)
    )

    user_content = f"""\
## Current System Prompt
{current_prompt or "(empty — no system prompt set)"}

## Failed Test Cases ({len(sorted_failures)} of {len(failed_items)} total failures)
{failures_text}

## Instructions
1. Analyze the root causes of these failures.
2. Propose targeted changes to the system prompt.
3. Generate the improved prompt.
"""

    try:
        resp = await client.chat.completions.create(
            model="gpt-5.4-mini",
            messages=[
                {"role": "system", "content": _REWRITER_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            max_tokens=4000,
        )
        raw = resp.choices[0].message.content or "{}"

        # Parse the JSON response, handling potential markdown wrapping
        json_str = raw.strip()
        if json_str.startswith("```"):
            # Strip markdown code fence
            lines = json_str.split("\n")
            json_str = "\n".join(lines[1:-1]) if len(lines) > 2 else json_str

        data = json.loads(json_str)

        return RewriteResult(
            original_prompt=current_prompt,
            improved_prompt=str(data.get("improved_prompt", current_prompt)),
            changelog=data.get("changelog", ["No changes proposed"]),
            failure_analysis=str(data.get("failure_analysis", "")),
            confidence=float(data.get("confidence", 0.5)),
        )

    except json.JSONDecodeError as exc:
        logger.warning("prompt_rewriter: JSON parse failed, returning raw text: %s", exc)
        # Fallback: return raw text as the improved prompt
        return RewriteResult(
            original_prompt=current_prompt,
            improved_prompt=raw if raw else current_prompt,
            changelog=["Rewriter output was not valid JSON — raw text used"],
            failure_analysis="Parse error during rewrite",
            confidence=0.2,
        )
    except Exception as exc:
        logger.error("prompt_rewriter failed: %s", exc)
        return RewriteResult(
            original_prompt=current_prompt,
            improved_prompt=current_prompt,
            changelog=[f"Rewrite failed: {exc}"],
            failure_analysis=f"Error: {exc}",
            confidence=0.0,
        )


async def rewrite_and_snapshot(
    pool,
    agent_id,
    workspace_id,
    user_id,
    current_prompt: str,
    failed_items: list[FailedItem],
    llm_config: dict[str, Any],
    *,
    openai_api_key: str | None = None,
) -> dict[str, Any] | None:
    """Full pipeline: rewrite prompt → create CANDIDATE genome → return info.

    This closes the feedback loop:
      eval failure → prompt rewrite → candidate genome → AB test → promote

    Returns dict with candidate_version_id, rewrite result, or None if no rewrite needed.
    """
    from flow.application.genome_service import snapshot_genome
    from flow.domain.genome import VersionStatus, VersionTrigger

    if not failed_items:
        return None

    rewrite = await rewrite_prompt(
        current_prompt=current_prompt,
        failed_items=failed_items,
        openai_api_key=openai_api_key,
    )

    # Only proceed if confidence is reasonable and prompt actually changed
    if rewrite.confidence < 0.3:
        logger.info(
            "prompt_rewriter.low_confidence",
            extra={"confidence": rewrite.confidence, "agent_id": str(agent_id)},
        )
        return None

    if rewrite.improved_prompt.strip() == current_prompt.strip():
        logger.info("prompt_rewriter.no_change", extra={"agent_id": str(agent_id)})
        return None

    # Update agent config with new prompt, then snapshot
    async with pool.acquire() as conn:
        agent_row = await conn.fetchrow(
            "SELECT config FROM agents WHERE id = $1 AND workspace_id = $2",
            agent_id,
            workspace_id,
        )
        if not agent_row:
            return None

        import json as _json

        config = agent_row["config"]
        if isinstance(config, str):
            config = _json.loads(config)
        config = dict(config or {})
        original_prompt_stored = config.get("system_prompt", current_prompt)

        # Write candidate prompt temporarily
        config["system_prompt"] = rewrite.improved_prompt
        config["_rewrite_changelog"] = rewrite.changelog
        await conn.execute(
            "UPDATE agents SET config = $1 WHERE id = $2 AND workspace_id = $3",
            config,
            agent_id,
            workspace_id,
        )

    candidate_id = None
    try:
        # Snapshot as CANDIDATE (reads the temporarily-updated config)
        candidate_id = await snapshot_genome(
            pool=pool,
            agent_id=agent_id,
            workspace_id=workspace_id,
            trigger=VersionTrigger.EVAL_PASS,
            status=VersionStatus.CANDIDATE,
            created_by=user_id,
        )
    except Exception:
        logger.exception(
            "prompt_rewriter.snapshot_failed",
            extra={"agent_id": str(agent_id)},
        )
    finally:
        # Always restore original prompt — candidate is independently snapshotted
        async with pool.acquire() as conn:
            config["system_prompt"] = original_prompt_stored
            config.pop("_rewrite_changelog", None)
            await conn.execute(
                "UPDATE agents SET config = $1 WHERE id = $2 AND workspace_id = $3",
                config,
                agent_id,
                workspace_id,
            )

    if candidate_id is None:
        return None

    logger.info(
        "prompt_rewriter.candidate_created",
        extra={
            "agent_id": str(agent_id),
            "candidate_id": str(candidate_id),
            "confidence": rewrite.confidence,
            "num_changes": len(rewrite.changelog),
        },
    )

    return {
        "candidate_version_id": str(candidate_id),
        "rewrite": {
            "changelog": rewrite.changelog,
            "failure_analysis": rewrite.failure_analysis,
            "confidence": rewrite.confidence,
            "prompt_diff_len": len(rewrite.improved_prompt) - len(current_prompt),
        },
    }
