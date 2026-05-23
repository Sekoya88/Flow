from __future__ import annotations


def register_research_digest_prompt(mcp):  # type: ignore[no-untyped-def]

    @mcp.prompt()
    def research_digest_summary(
        title: str,
        abstract: str,
        categories: str = "",
        relevance_score: float = 0.0,
    ) -> str:
        """Generate a structured Obsidian research note from a paper."""
        return f"""You are a research analyst for an AI/ML team.

Given this paper:
**Title**: {title}
**Categories**: {categories}
**Relevance score**: {relevance_score:.2f}

**Abstract**:
{abstract}

Generate a structured Obsidian note with these sections:
1. **TL;DR** — one sentence summary
2. **Key Insights** — 3-5 bullet points
3. **Practical Applications** — 2-3 concrete use cases
4. **Models & Datasets cited** — brief list
5. **Personal Notes** — leave blank (placeholder for user)

Use concise, technical language. Focus on actionable insights for an ML practitioner."""
