"""Tests for project reference-note helpers (pure functions)."""

from __future__ import annotations

from flow.interfaces.http.routes.projects import _paper_reference_md, _slugify


def test_slugify_strips_unsafe_chars() -> None:
    assert _slugify("Gaze Heads: How VLMs Look") == "Gaze-Heads-How-VLMs-Look"
    assert _slugify("a/b:c") == "abc"
    assert _slugify("") == "paper"


def test_slugify_caps_length() -> None:
    assert len(_slugify("word " * 50)) <= 80


def test_paper_reference_md_has_frontmatter_and_sections() -> None:
    md = _paper_reference_md(
        {
            "title": 'A "Quoted" Title',
            "arxiv_id": "2501.00001",
            "authors": ["Ada", "Linus"],
            "categories": ["cs.AI"],
            "tldr": "Short summary.",
            "abstract": "Long abstract.",
            "key_insights": ["one", "two"],
            "relevance_score": 0.83,
            "source_url": "https://example.com/p",
        }
    )
    assert md.startswith("---\n")
    assert 'title: "A \'Quoted\' Title"' in md
    assert "relevance_score: 0.83" in md
    assert "## Abstract" in md
    assert "- one" in md and "- two" in md
    assert "https://example.com/p" in md


def test_paper_reference_md_tolerates_missing_fields() -> None:
    md = _paper_reference_md({"title": "Bare"})
    assert "# Bare" in md
    assert "type: reference" in md
