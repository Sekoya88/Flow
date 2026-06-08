"""Generate golden evaluation items from a skill body via an LLM.

Returns structured items the caller persists into golden_sets/golden_items and
echoes to the front-end for transparency (prompt + per-item rationale).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from openai import AsyncOpenAI

from flow.infrastructure.observability.logging import get_logger

log = get_logger("flow.golden_generator")

_SYSTEM = """\
You are an evaluation-set designer. Given an AI skill (a system prompt), produce a small,
high-signal golden test set. Each item must be answerable using ONLY the skill, with a
verifiable expected output and concrete, gradable scoring criteria.

Return ONLY valid JSON:
{"items": [
  {"input_text": "...", "expected_output": "...", "scoring_criteria": "concrete 0-10 rubric", "rationale": "what this item probes"}
]}
Rules: cover the happy path, one edge case, and one failure/abuse case. No prose outside JSON.
"""


@dataclass
class GeneratedItem:
    input_text: str
    expected_output: str
    scoring_criteria: str
    rationale: str


def build_generation_prompt(*, skill_name: str, skill_body: str, n: int) -> str:
    return (
        f"## Skill name\n{skill_name}\n\n"
        f"## Skill body (system prompt)\n{skill_body[:6000]}\n\n"
        f"## Task\nProduce exactly {n} golden items as specified."
    )


def parse_generation_response(raw: str) -> list[GeneratedItem]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        log.warning("golden_generator.parse_failed")
        return []
    out: list[GeneratedItem] = []
    for it in data.get("items", []):
        try:
            out.append(
                GeneratedItem(
                    input_text=str(it["input_text"]).strip(),
                    expected_output=str(it["expected_output"]).strip(),
                    scoring_criteria=str(it.get("scoring_criteria", "")).strip(),
                    rationale=str(it.get("rationale", "")).strip(),
                )
            )
        except (KeyError, TypeError):
            continue
    return out


async def generate_golden_items(
    *, skill_name: str, skill_body: str, n: int = 5, client: AsyncOpenAI | None = None
) -> tuple[list[GeneratedItem], str]:
    """Return (items, prompt_used). Empty list on any failure — never raises."""
    prompt = build_generation_prompt(skill_name=skill_name, skill_body=skill_body, n=n)
    if client is None:
        api_key = os.environ.get("FLOW_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        client = AsyncOpenAI(api_key=api_key)
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=2000,
        )
        return parse_generation_response(resp.choices[0].message.content or ""), prompt
    except Exception as exc:  # noqa: BLE001
        log.error("golden_generator.failed", error=str(exc))
        return [], prompt
