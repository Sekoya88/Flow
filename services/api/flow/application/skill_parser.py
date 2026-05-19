"""Parse SKILL.md format: YAML frontmatter + markdown body.

Format:
---
name: skill-name
description: When to use this skill
version: "1.2"
allowed-tools: fetch_url, sandbox
triggers:
  - "user asks about LangGraph"
  - "documentation lookup"
metadata:
  author: flow-agent
  domain: research
---

# Skill Name

## Instructions
...actual skill content...
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml


@dataclass
class ParsedSkill:
    name: str
    description: str = ""
    # Display label from YAML frontmatter (e.g. "1.0", "2.1"). NOT the DB integer version —
    # the DB uses MAX(version)+1 via upsert_agent_skill and never reads this field.
    version: str = "1.0"
    allowed_tools: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    body_md: str = ""

    def to_frontmatter_md(self) -> str:
        """Serialize back to SKILL.md format."""
        fm: dict = {"name": self.name}
        if self.description:
            fm["description"] = self.description
        if self.version != "1.0":
            fm["version"] = self.version
        if self.allowed_tools:
            fm["allowed-tools"] = ", ".join(self.allowed_tools)
        if self.triggers:
            fm["triggers"] = self.triggers
        if self.metadata:
            fm["metadata"] = self.metadata
        header = yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip()
        return f"---\n{header}\n---\n\n{self.body_md}"


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def parse_skill_md(content: str) -> ParsedSkill:
    """Parse a SKILL.md string into structured data."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return ParsedSkill(name="unnamed", body_md=content.strip())

    raw_fm = match.group(1)
    body = content[match.end() :].strip()

    try:
        fm = yaml.safe_load(raw_fm) or {}
    except yaml.YAMLError:
        return ParsedSkill(name="unnamed", body_md=content.strip())

    allowed_tools_raw = fm.get("allowed-tools", "")
    if isinstance(allowed_tools_raw, str):
        allowed_tools = [t.strip() for t in allowed_tools_raw.split(",") if t.strip()]
    elif isinstance(allowed_tools_raw, list):
        allowed_tools = allowed_tools_raw
    else:
        allowed_tools = []

    return ParsedSkill(
        name=fm.get("name", "unnamed"),
        description=fm.get("description", ""),
        version=str(fm.get("version", "1.0")),
        allowed_tools=allowed_tools,
        triggers=fm.get("triggers", []) if isinstance(fm.get("triggers"), list) else [],
        metadata=fm.get("metadata", {}) if isinstance(fm.get("metadata"), dict) else {},
        body_md=body,
    )


def skill_matches_query(skill: ParsedSkill, query: str) -> bool:
    """Progressive disclosure: check if skill is relevant to the query."""
    query_lower = query.lower()
    for trigger in skill.triggers:
        if any(word in query_lower for word in trigger.lower().split()):
            return True
    if skill.name.lower() in query_lower:
        return True
    if skill.description and any(word in query_lower for word in skill.description.lower().split()[:5]):
        return True
    return False
