"""LLM-judge gate for post-run memory extraction."""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

_FACT_EXTRACTION_PROMPT = """\
You are a memory curator. Given a user question and an AI answer, extract at most 3 short, \
atomic facts that are worth remembering for future runs. Output ONLY a JSON array of strings. \
Example: ["Fact A.", "Fact B."]. If nothing is worth storing, return [].

Question: {question}

Answer:
{answer}
"""

_PATTERN_SUMMARY_PROMPT = """\
You are a planning archivist. Given a user question and an AI answer, write:
1. PROBLEM: one sentence describing the type of problem (no specific details).
2. SOLUTION: 3-5 bullet steps that solved it (generic, reusable).

Output ONLY valid JSON: {{"problem": "...", "solution": "step1\\nstep2\\nstep3"}}

Question: {question}
Answer:
{answer}
"""


async def extract_facts_from_answer(llm, question: str, answer: str) -> list[str]:
    """Call LLM to extract atomic facts. Returns [] on any failure."""
    try:
        prompt = _FACT_EXTRACTION_PROMPT.format(
            question=question[:500], answer=answer[:2000]
        )
        from langchain_core.messages import HumanMessage
        out = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = str(out.content).strip()
        facts = json.loads(raw)
        if isinstance(facts, list):
            return [str(f) for f in facts[:3]]
        return []
    except Exception as exc:
        logger.debug("fact extraction failed: %s", exc)
        return []


async def should_store_pattern(confidence: float, answer_len: int) -> bool:
    """Heuristic gate: store pattern only for high-quality, substantive runs."""
    return confidence >= 0.8 and answer_len >= 100


async def extract_pattern_summary(llm, question: str, answer: str) -> tuple[str, str] | None:
    """Extract (problem_summary, solution_steps) for ReasoningBank. Returns None on failure."""
    try:
        prompt = _PATTERN_SUMMARY_PROMPT.format(
            question=question[:500], answer=answer[:2000]
        )
        from langchain_core.messages import HumanMessage
        out = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = str(out.content).strip()
        data = json.loads(raw)
        if isinstance(data, dict) and "problem" in data and "solution" in data:
            return str(data["problem"])[:500], str(data["solution"])[:2000]
        return None
    except Exception as exc:
        logger.debug("pattern extraction failed: %s", exc)
        return None
