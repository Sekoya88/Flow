"""Tests for skill_rewriter.py — frontmatter preservation, version bump, LLM fallback."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from flow.application.prompt_rewriter import FailedItem
from flow.application.skill_rewriter import (
    SkillRewriteResult,
    _bump_version_in_frontmatter,
    _split_frontmatter,
    rewrite_skill,
)

_SKILL_MD = """\
---
name: research-report
description: Produce a structured research report
version: '1.2'
triggers:
  - research report
  - market analysis
---

## Instructions
Write a structured research report.
"""


# ── Unit: frontmatter helpers ────────────────────────────────────────────────


def test_split_frontmatter_returns_front_and_body():
    front, body = _split_frontmatter(_SKILL_MD)
    assert "version: '1.2'" in front
    assert "## Instructions" in body
    assert "---" not in body.lstrip()


def test_split_frontmatter_no_frontmatter():
    md = "# Just a plain body\nNo YAML here."
    front, body = _split_frontmatter(md)
    assert front == ""
    assert body == md


def test_bump_version_increments_patch():
    front = "---\nname: foo\nversion: '1.2'\n---"
    bumped = _bump_version_in_frontmatter(front)
    assert "version: '1.3'" in bumped


def test_bump_version_handles_integer_version():
    front = "---\nversion: 2\n---"
    bumped = _bump_version_in_frontmatter(front)
    assert "version: '3'" in bumped or "version: 3" in bumped


# ── rewrite_skill: happy path ────────────────────────────────────────────────


def _fake_llm_response(content: str) -> MagicMock:
    resp = MagicMock()
    resp.choices[0].message.content = content
    return resp


@pytest.mark.asyncio
async def test_rewrite_skill_returns_improved_content():
    new_body = "## Instructions\nWrite a well-structured, comprehensive report."
    llm_payload = json.dumps(
        {
            "failure_analysis": "Reports lacked depth.",
            "changelog": ["Added depth guidance"],
            "improved_body_md": new_body,
            "confidence": 0.85,
        }
    )

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_fake_llm_response(llm_payload))

    failed = [FailedItem("What is X?", "X is Y.", "X.", 0.3, "Too short")]
    result = await rewrite_skill(_SKILL_MD, failed, client=mock_client)

    assert isinstance(result, SkillRewriteResult)
    assert result.confidence == 0.85
    assert "Added depth guidance" in result.changelog
    assert "research-report" in result.improved_content_md  # frontmatter preserved
    assert "version: '1.3'" in result.improved_content_md  # version bumped
    assert new_body.strip() in result.improved_content_md


@pytest.mark.asyncio
async def test_rewrite_skill_preserves_frontmatter_intact():
    new_body = "New body content."
    llm_payload = json.dumps(
        {
            "failure_analysis": "Something failed.",
            "changelog": ["Fix"],
            "improved_body_md": new_body,
            "confidence": 0.7,
        }
    )
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_fake_llm_response(llm_payload))

    failed = [FailedItem("Q", "A", "wrong", 0.2, "bad")]
    result = await rewrite_skill(_SKILL_MD, failed, client=mock_client)

    # Triggers and allowed_tools should remain in frontmatter
    assert "triggers:" in result.improved_content_md
    assert "research report" in result.improved_content_md


@pytest.mark.asyncio
async def test_rewrite_skill_json_parse_error_returns_no_change():
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_fake_llm_response("not json at all"))

    failed = [FailedItem("Q", "A", "wrong", 0.1, "bad")]
    result = await rewrite_skill(_SKILL_MD, failed, client=mock_client)

    assert result.confidence == 0.2
    assert result.improved_content_md == _SKILL_MD
    assert "not valid JSON" in result.changelog[0]


@pytest.mark.asyncio
async def test_rewrite_skill_llm_exception_returns_no_change():
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=Exception("api error"))

    failed = [FailedItem("Q", "A", "wrong", 0.1, "bad")]
    result = await rewrite_skill(_SKILL_MD, failed, client=mock_client)

    assert result.confidence == 0.0
    assert result.improved_content_md == _SKILL_MD


@pytest.mark.asyncio
async def test_rewrite_skill_limits_failures_to_max():
    new_body = "Better body."
    llm_payload = json.dumps(
        {
            "failure_analysis": "analysis",
            "changelog": ["c"],
            "improved_body_md": new_body,
            "confidence": 0.8,
        }
    )
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_fake_llm_response(llm_payload))

    # Send 10 failures but max_failures=3
    failed = [FailedItem(f"Q{i}", "A", "wrong", 0.1 * i, "bad") for i in range(10)]
    await rewrite_skill(_SKILL_MD, failed, max_failures=3, client=mock_client)

    call_args = mock_client.chat.completions.create.call_args
    user_content = call_args.kwargs["messages"][1]["content"]
    # Only 3 failure blocks should appear
    assert user_content.count("--- FAILURE") == 3
