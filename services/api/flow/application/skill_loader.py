"""Centralized Skill Loader — Phase 1.

Responsible for:
  1. Loading active skills from the DB for a given agent
  2. Matching skills against a user query (progressive disclosure)
  3. Formatting matched skills as structured XML for system prompt injection
  4. Logging skill usage events for observability

Replaces the inline skill-loading logic in nodes.py:make_planner.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from flow.application.skill_parser import ParsedSkill, parse_skill_md, skill_matches_query
from flow.infrastructure.persistence.repo import FlowRepository

logger = logging.getLogger(__name__)


@dataclass
class MatchedSkill:
    """A skill that matched against the user query."""

    skill_id: UUID
    name: str
    version: str
    description: str
    score: float
    use_count: int
    allowed_tools: list[str]
    triggers: list[str]
    body_md: str
    content_md: str  # full original SKILL.md content
    parsed: ParsedSkill


class SkillLoader:
    """Centralized skill loading, matching, and injection."""

    def __init__(self, repo: FlowRepository) -> None:
        self._repo = repo

    async def load_and_match(
        self,
        agent_id: UUID,
        workspace_id: UUID,
        query: str,
        *,
        execution_id: UUID | None = None,
        max_skills: int = 5,
        use_bandit: bool = True,
    ) -> list[MatchedSkill]:
        """Load active skills, match against query, return ranked list.

        Candidates are first filtered by trigger match. The surviving set is then
        ordered either by the per-skill RL bandit (Thompson Sampling over the
        learned Beta posteriors, when ``use_bandit``) or by static ``score`` DESC.
        The bandit closes the reward loop: grades written by the reflector now
        decide which skills actually load.
        """
        try:
            skills = await self._repo.list_active_skills(agent_id, workspace_id)
        except Exception:
            logger.debug("skill_loader.list_failed", exc_info=True)
            return []

        if not skills:
            return []

        matched: list[MatchedSkill] = []
        for s in skills:
            parsed = parse_skill_md(s["content_md"])
            if not skill_matches_query(parsed, query):
                continue

            matched.append(
                MatchedSkill(
                    skill_id=s["id"],
                    name=parsed.name,
                    version=parsed.version,
                    description=parsed.description,
                    score=float(s.get("score") or 0.0),
                    use_count=int(s.get("use_count") or 0),
                    allowed_tools=parsed.allowed_tools,
                    triggers=parsed.triggers,
                    body_md=parsed.body_md,
                    content_md=s["content_md"],
                    parsed=parsed,
                )
            )

            # Increment use count + log match event
            try:
                await self._repo.increment_skill_use(s["id"])
                await self._repo.log_skill_match(
                    skill_id=s["id"],
                    workspace_id=workspace_id,
                    execution_id=execution_id,
                    matched_text=query[:500] if query else None,
                )
            except Exception:
                pass  # observability is best-effort

        # Static fallback ordering: score DESC.
        matched.sort(key=lambda m: m.score, reverse=True)

        # Bandit ordering: let the learned Beta posteriors pick which skills load,
        # so the reflector's reward signal actually drives selection. Best-effort —
        # any failure (no arms, DB hiccup) falls back to the score sort above.
        if use_bandit and matched:
            try:
                from flow.application.rl_bandit import SkillBandit

                bandit = SkillBandit(self._repo._pool)
                ordered_ids = await bandit.select_skills(
                    agent_id,
                    [m.skill_id for m in matched],
                    k=max_skills,
                )
                if ordered_ids:
                    by_id = {m.skill_id: m for m in matched}
                    selected = [by_id[sid] for sid in ordered_ids if sid in by_id]
                    tail = [m for m in matched if m.skill_id not in set(ordered_ids)]
                    matched = selected + tail
            except Exception:
                logger.debug("skill_loader.bandit_select_failed", exc_info=True)

        return matched[:max_skills]

    def format_xml(self, skills: list[MatchedSkill]) -> str:
        """Format matched skills as XML block for system prompt injection.

        Example output:
        <skills>
          <skill name="research-arxiv" version="2.1" score="0.87">
            <description>When to use this skill</description>
            <triggers>arxiv, paper, research</triggers>
            <allowed_tools>fetch_webpage, sandbox</allowed_tools>
            <body>## Instructions...</body>
          </skill>
        </skills>
        """
        if not skills:
            return ""

        lines = ["<skills>"]
        for s in skills:
            lines.append(f'  <skill name="{_xml_escape(s.name)}" version="{_xml_escape(s.version)}" score="{s.score:.2f}">')
            if s.description:
                lines.append(f"    <description>{_xml_escape(s.description)}</description>")
            if s.triggers:
                lines.append(f"    <triggers>{', '.join(s.triggers)}</triggers>")
            if s.allowed_tools:
                lines.append(f"    <allowed_tools>{', '.join(s.allowed_tools)}</allowed_tools>")
            # Truncate body to avoid blowing up context window
            body = s.body_md[:1500] if s.body_md else ""
            if body:
                lines.append(f"    <body>{_xml_escape(body)}</body>")
            lines.append("  </skill>")
        lines.append("</skills>")
        return "\n".join(lines)

    def format_plain(self, skills: list[MatchedSkill]) -> str:
        """Format matched skills as plain text (legacy format, fallback)."""
        if not skills:
            return ""

        parts = []
        for s in skills:
            parts.append(
                f"[Skill: {s.name} v{s.version}]\n"
                f"Description: {s.description}\n"
                f"Allowed tools: {', '.join(s.allowed_tools) or 'any'}\n\n"
                f"{s.body_md[:800]}"
            )
        return "\n\n---\n\n".join(parts)

    def to_state_dicts(self, skills: list[MatchedSkill]) -> list[dict[str, Any]]:
        """Convert matched skills to serializable dicts for FlowGraphState."""
        return [
            {
                "skill_id": str(s.skill_id),
                "name": s.name,
                "version": s.version,
                "score": s.score,
                "allowed_tools": s.allowed_tools,
                "triggers": s.triggers,
            }
            for s in skills
        ]


def _xml_escape(text: str) -> str:
    """Minimal XML escaping for attribute values and text content."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
