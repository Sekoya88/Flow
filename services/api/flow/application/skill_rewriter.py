"""Skill Rewriter — mirrors prompt_rewriter.py for the skill improvement loop.

Given a SKILL.md and failed golden-set items linked to that skill, generates
an improved skill body while preserving YAML frontmatter (only bumps version).

Design matches prompt_rewriter.py:
  1. Surgical edits to the markdown body — frontmatter is write-protected.
  2. Changelog + confidence output for proposal review.
  3. JSON response format for deterministic parsing.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

from flow.application.prompt_rewriter import FailedItem  # reuse the shared dataclass

logger = logging.getLogger(__name__)


@dataclass
class SkillRewriteResult:
    """Output of the skill rewriter."""

    original_content_md: str
    improved_content_md: str
    changelog: list[str]
    failure_analysis: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


_SKILL_REWRITER_SYSTEM = """\
You are an expert AI skill engineer. A "skill" is a SKILL.md file used as a
system prompt for an AI agent. Skills have YAML frontmatter (---) and a markdown
body.

Your task: Given the SKILL.md body and failed test cases, improve the body so
the skill handles those failures while preserving existing strengths.

## Rules
1. **Never touch the YAML frontmatter.** Only edit the body below the closing ---.
2. **Surgical edits.** Targeted insertions/clarifications, not wholesale rewrites.
3. **No regressions.** Don't remove instructions that help passing items.
4. **Concrete guidance.** Add specific behavioral rules, not vague guidance.
5. **Keep markdown structure.** Preserve existing headings and formatting style.

## Output Format
Return ONLY valid JSON:
{
  "failure_analysis": "Brief root-cause analysis (2-4 sentences)",
  "changelog": ["Change 1: ...", "Change 2: ..."],
  "improved_body_md": "The full improved markdown body (no frontmatter)",
  "confidence": 0.85
}
"""


def _split_frontmatter(content_md: str) -> tuple[str, str]:
    """Split SKILL.md into (frontmatter_block, body_md).

    Returns (frontmatter_with_fences, body) or ("", content_md) if no frontmatter.
    """
    if not content_md.lstrip().startswith("---"):
        return "", content_md
    # Find the closing ---
    after_open = content_md.index("---") + 3
    rest = content_md[after_open:]
    close = rest.find("---")
    if close == -1:
        return "", content_md
    front = content_md[: after_open + close + 3]
    body = content_md[after_open + close + 3 :].lstrip("\n")
    return front, body


def _bump_version_in_frontmatter(frontmatter: str) -> str:
    """Increment version string inside YAML frontmatter."""

    def _inc(m: re.Match) -> str:
        parts = m.group(1).split(".")
        try:
            parts[-1] = str(int(parts[-1]) + 1)
        except ValueError:
            parts.append("1")
        joined = ".".join(parts)
        return f"version: '{joined}'"

    updated = re.sub(r"version:\s*['\"]?([\d.]+)['\"]?", _inc, frontmatter)
    return updated


async def rewrite_skill(
    current_content_md: str,
    failed_items: list[FailedItem],
    *,
    max_failures: int = 5,
    client: AsyncOpenAI | None = None,
    openai_api_key: str | None = None,
) -> SkillRewriteResult:
    """Analyze failures and produce an improved SKILL.md (frontmatter preserved, version bumped).

    Args:
        current_content_md: Full SKILL.md content.
        failed_items: Items that scored below the pass threshold.
        max_failures: Cap on failures sent to LLM (context budget).
        client: Optional pre-configured OpenAI client.
        openai_api_key: API key fallback.
    """
    if client is None:
        api_key = openai_api_key or os.environ.get("FLOW_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        client = AsyncOpenAI(api_key=api_key)

    frontmatter, body_md = _split_frontmatter(current_content_md)

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
## Current Skill Body (below the YAML frontmatter)
{body_md or "(empty body)"}

## Failed Test Cases ({len(sorted_failures)} of {len(failed_items)} total)
{failures_text}

## Instructions
1. Analyze the root causes of these failures.
2. Propose targeted edits to the skill body.
3. Return the complete improved body (no frontmatter — I will prepend it).
"""

    raw = ""
    try:
        resp = await client.chat.completions.create(
            model="gpt-5.4-mini",
            messages=[
                {"role": "system", "content": _SKILL_REWRITER_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            max_tokens=4000,
        )
        raw = resp.choices[0].message.content or "{}"

        json_str = raw.strip()
        if json_str.startswith("```"):
            lines = json_str.split("\n")
            json_str = "\n".join(lines[1:-1]) if len(lines) > 2 else json_str

        data = json.loads(json_str)
        new_body = str(data.get("improved_body_md", body_md))
        bumped_front = _bump_version_in_frontmatter(frontmatter) if frontmatter else frontmatter
        improved_md = (bumped_front + "\n\n" + new_body) if bumped_front else new_body

        return SkillRewriteResult(
            original_content_md=current_content_md,
            improved_content_md=improved_md,
            changelog=data.get("changelog", ["No changes proposed"]),
            failure_analysis=str(data.get("failure_analysis", "")),
            confidence=float(data.get("confidence", 0.5)),
        )

    except json.JSONDecodeError as exc:
        logger.warning("skill_rewriter: JSON parse failed: %s", exc)
        return SkillRewriteResult(
            original_content_md=current_content_md,
            improved_content_md=current_content_md,
            changelog=["Rewriter output was not valid JSON — no change applied"],
            failure_analysis="JSON parse error",
            confidence=0.2,
        )
    except Exception as exc:
        logger.error("skill_rewriter failed: %s", exc)
        return SkillRewriteResult(
            original_content_md=current_content_md,
            improved_content_md=current_content_md,
            changelog=[f"Rewrite failed: {exc}"],
            failure_analysis=f"Error: {exc}",
            confidence=0.0,
        )
