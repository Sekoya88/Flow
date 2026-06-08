"""Curated skill collections — the source of truth for the Skill Hub marketplace.

Each collection pins exact SKILL.md paths in a public GitHub repo so import does not
depend on the GitHub tree API (60 req/hr unauthenticated). Content is fetched from
raw.githubusercontent.com, which is not rate-limited the same way.
"""

from __future__ import annotations

import re

# ── Filtering ────────────────────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
# Paths that look like skills but are support material, not installable skills.
_EXCLUDE_DIR_RE = re.compile(r"(^|/)(references|assets|scripts|examples|templates|docs|deprecated)(/|$)", re.IGNORECASE)


def is_skill_file(path: str, content: str) -> bool:
    """True only for installable skills: a file literally named SKILL.md, OR a .md
    file whose frontmatter declares both `name` and `description`. README/reference/
    template/example/deprecated files are rejected even if they carry frontmatter."""
    lower = path.lower()
    if not lower.endswith(".md"):
        return False
    if _EXCLUDE_DIR_RE.search(path):
        return False
    if lower.endswith("/skill.md") or lower == "skill.md":
        return True
    if lower.endswith("readme.md") or lower.endswith("contributing.md") or lower.endswith("changelog.md"):
        return False
    m = _FRONTMATTER_RE.match(content.lstrip())
    if not m:
        return False
    fm = m.group(1)
    return bool(re.search(r"^name\s*:", fm, re.MULTILINE)) and bool(re.search(r"^description\s*:", fm, re.MULTILINE))


def raw_url(repo: str, path: str) -> str:
    """Build a raw.githubusercontent.com URL for `repo` ('owner/name') at HEAD."""
    return f"https://raw.githubusercontent.com/{repo}/HEAD/{path}"


def _skill(path: str) -> dict:
    """Derive a display name from the parent folder of a SKILL.md path."""
    parts = [p for p in path.split("/") if p and p != "SKILL.md"]
    name = parts[-1] if parts else path
    return {"path": path, "name": name}


# ── Manifest ─────────────────────────────────────────────────────────────────
# Paths verified against each repo's HEAD tree on 2026-06-08.

CURATED_COLLECTIONS: list[dict] = [
    {
        "id": "mattpocock-skills",
        "name": "Matt Pocock — Engineering & Productivity",
        "description": "Battle-tested dev workflow skills: TDD, diagnosis, PRDs, issue breakdown, skill authoring.",
        "repo": "mattpocock/skills",
        "category": "Code",
        "skills": [
            _skill("skills/engineering/tdd/SKILL.md"),
            _skill("skills/engineering/diagnose/SKILL.md"),
            _skill("skills/engineering/to-prd/SKILL.md"),
            _skill("skills/engineering/to-issues/SKILL.md"),
            _skill("skills/engineering/improve-codebase-architecture/SKILL.md"),
            _skill("skills/productivity/write-a-skill/SKILL.md"),
            _skill("skills/productivity/handoff/SKILL.md"),
            _skill("skills/misc/setup-pre-commit/SKILL.md"),
        ],
    },
    {
        "id": "scientific-agent-skills",
        "name": "K-Dense — Scientific Agent Skills",
        "description": "Domain skills for scientific computing & bioinformatics: biopython, astropy, deepchem, clinical decision support.",
        "repo": "K-Dense-AI/scientific-agent-skills",
        "category": "Research",
        "skills": [
            _skill("skills/biopython/SKILL.md"),
            _skill("skills/astropy/SKILL.md"),
            _skill("skills/deepchem/SKILL.md"),
            _skill("skills/citation-management/SKILL.md"),
            _skill("skills/clinical-decision-support/SKILL.md"),
            _skill("skills/database-lookup/SKILL.md"),
        ],
    },
    {
        "id": "academic-research-skills",
        "name": "Academic Research Suite",
        "description": "End-to-end academic writing pipeline: paper drafting, peer review, full pipeline, and deep research.",
        "repo": "Imbad0202/academic-research-skills",
        "category": "Research",
        "skills": [
            _skill("academic-paper/SKILL.md"),
            _skill("academic-paper-reviewer/SKILL.md"),
            _skill("academic-pipeline/SKILL.md"),
            _skill("deep-research/SKILL.md"),
        ],
    },
    {
        "id": "ecc",
        "name": "ECC — Everything Claude Code",
        "description": "Reference agent skills for product engineering: API design, security review, TDD workflow, market & deep research.",
        "repo": "affaan-m/ECC",
        "category": "Code",
        "skills": [
            _skill(".agents/skills/api-design/SKILL.md"),
            _skill(".agents/skills/security-review/SKILL.md"),
            _skill(".agents/skills/tdd-workflow/SKILL.md"),
            _skill(".agents/skills/deep-research/SKILL.md"),
            _skill(".agents/skills/market-research/SKILL.md"),
            _skill(".agents/skills/documentation-lookup/SKILL.md"),
        ],
    },
]


def get_collection(collection_id: str) -> dict | None:
    return next((c for c in CURATED_COLLECTIONS if c["id"] == collection_id), None)
