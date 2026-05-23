"""Unit tests for research_digest_graph nodes (no DB, no external calls)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flow.infrastructure.graph.research_digest_graph import (
    DigestState,
    fetch_sources,
    filter_by_interest,
    format_obsidian,
    summarize_papers,
)


def _make_state(**overrides) -> DigestState:
    base: DigestState = {
        "workspace_id": "00000000-0000-0000-0000-000000000001",
        "config": {
            "arxiv_categories": ["cs.AI", "cs.LG"],
            "min_relevance_score": 0.5,
        },
        "raw_papers": [],
        "filtered_papers": [],
        "enriched_papers": [],
        "obsidian_notes": [],
        "persisted_ids": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def _paper(**overrides) -> dict:
    base = {
        "title": "Test Paper on AI",
        "abstract": "A study of AI systems.",
        "source_url": "https://arxiv.org/abs/2501.00001",
        "arxiv_id": "2501.00001",
        "authors": ["Alice", "Bob"],
        "categories": ["cs.AI"],
        "published_at": "2026-01-01T00:00:00",
    }
    return {**base, **overrides}


# ── fetch_sources ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_sources_returns_raw_papers():
    """fetch_sources returns a list (may be empty if arxiv unavailable)."""
    with patch("arxiv.Client") as mock_client_cls, patch("httpx.AsyncClient") as mock_http:
        mock_results = MagicMock()
        mock_results.__iter__ = MagicMock(return_value=iter([]))
        mock_client_cls.return_value.results.return_value = mock_results
        mock_resp = MagicMock(status_code=200)
        mock_resp.headers.get.return_value = "application/json"
        mock_resp.json.return_value = []
        mock_http.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await fetch_sources(_make_state())

    assert "raw_papers" in result
    assert isinstance(result["raw_papers"], list)


@pytest.mark.asyncio
async def test_fetch_sources_handles_arxiv_failure():
    """fetch_sources continues even when arxiv raises."""
    with patch("arxiv.Client", side_effect=Exception("network down")), patch("httpx.AsyncClient") as mock_http:
        mock_resp = MagicMock(status_code=200)
        mock_resp.headers.get.return_value = "application/json"
        mock_resp.json.return_value = []
        mock_http.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await fetch_sources(_make_state())
    assert isinstance(result["raw_papers"], list)


# ── filter_by_interest ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_filter_drops_no_title():
    """Papers without title are excluded."""
    state = _make_state(raw_papers=[_paper(title=""), _paper()])
    with patch("flow.config.get_settings") as mock_settings, patch("flow.infrastructure.llm.providers.get_chat_model", return_value=None):
        mock_settings.return_value = MagicMock(openai_api_key=None, anthropic_api_key=None)
        result = await filter_by_interest(state)
    assert all(p["title"] for p in result["filtered_papers"])


@pytest.mark.asyncio
async def test_filter_category_mismatch_scores_low():
    """Paper with no matching category gets low score and is filtered out."""
    state = _make_state(
        raw_papers=[_paper(categories=["econ.GN"])],
        config={"arxiv_categories": ["cs.AI"], "min_relevance_score": 0.5},
    )
    with patch("flow.config.get_settings") as mock_settings, patch("flow.infrastructure.llm.providers.get_chat_model", return_value=None):
        mock_settings.return_value = MagicMock(openai_api_key=None, anthropic_api_key=None)
        result = await filter_by_interest(state)
    # econ.GN != cs.AI → relevance_score 0.2 < 0.5 → filtered out
    assert result["filtered_papers"] == []


@pytest.mark.asyncio
async def test_filter_category_match_survives_without_llm():
    """Paper with matching category survives filter even when LLM unavailable."""
    state = _make_state(raw_papers=[_paper(categories=["cs.AI"])])
    with patch("flow.config.get_settings") as mock_settings, patch("flow.infrastructure.llm.providers.get_chat_model", return_value=None):
        mock_settings.return_value = MagicMock(openai_api_key=None, anthropic_api_key=None)
        result = await filter_by_interest(state)
    # No LLM → fallback score 0.6 ≥ 0.5 → kept
    assert len(result["filtered_papers"]) == 1


@pytest.mark.asyncio
async def test_filter_uses_llm_score():
    """filter_by_interest uses LLM score when available."""
    state = _make_state(raw_papers=[_paper()])
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content='{"score": 0.9}'))
    with patch("flow.config.get_settings") as mock_settings, patch("flow.infrastructure.llm.providers.get_chat_model", return_value=mock_llm):
        mock_settings.return_value = MagicMock(openai_api_key="k", anthropic_api_key=None)
        result = await filter_by_interest(state)
    assert result["filtered_papers"][0]["relevance_score"] == pytest.approx(0.9)


# ── summarize_papers ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_summarize_no_llm_returns_none_fields():
    """Without LLM, tldr and key_insights are None."""
    state = _make_state(filtered_papers=[_paper()])
    with patch("flow.config.get_settings") as mock_settings, patch("flow.infrastructure.llm.providers.get_chat_model", return_value=None):
        mock_settings.return_value = MagicMock(openai_api_key=None, anthropic_api_key=None)
        result = await summarize_papers(state)
    assert result["enriched_papers"][0]["tldr"] is None


@pytest.mark.asyncio
async def test_summarize_parses_llm_json():
    """summarize_papers parses LLM JSON response into tldr + key_insights."""
    state = _make_state(filtered_papers=[_paper()])
    llm_response = MagicMock(content='{"tldr": "Short summary.", "key_insights": "- Point A"}')
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=llm_response)
    with patch("flow.config.get_settings") as mock_settings, patch("flow.infrastructure.llm.providers.get_chat_model", return_value=mock_llm):
        mock_settings.return_value = MagicMock(openai_api_key="k", anthropic_api_key=None)
        result = await summarize_papers(state)
    paper = result["enriched_papers"][0]
    assert paper["tldr"] == "Short summary."
    assert "Point A" in paper["key_insights"]


# ── format_obsidian ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_format_obsidian_has_yaml_frontmatter():
    """format_obsidian generates YAML frontmatter with required fields."""
    paper = _paper(relevance_score=0.85, tldr="TL;DR text", key_insights="- Insight A")
    state = _make_state(enriched_papers=[paper])
    result = await format_obsidian(state)
    note = result["obsidian_notes"][0]
    content = note["content"]
    assert content.startswith("---")
    assert "arxiv_id:" in content
    assert "relevance_score:" in content
    assert "status: unread" in content
    assert "type: research-paper" in content


@pytest.mark.asyncio
async def test_format_obsidian_path_uses_arxiv_id():
    """Note path uses arxiv_id as filename."""
    paper = _paper(arxiv_id="2501.99999", relevance_score=0.7)
    state = _make_state(enriched_papers=[paper])
    result = await format_obsidian(state)
    assert "2501.99999" in result["obsidian_notes"][0]["path"]


@pytest.mark.asyncio
async def test_format_obsidian_daily_link_present():
    """Note content includes a daily digest wikilink."""
    paper = _paper(relevance_score=0.7)
    state = _make_state(enriched_papers=[paper])
    result = await format_obsidian(state)
    assert "[[Research/Digest/" in result["obsidian_notes"][0]["content"]
