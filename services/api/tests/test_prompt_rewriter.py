"""Tests for the prompt rewriter — the core of the self-improvement loop."""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from flow.application.prompt_rewriter import (
    FailedItem,
    RewriteResult,
    rewrite_prompt,
    rewrite_and_snapshot,
)


def _make_failed_items(n=3) -> list[FailedItem]:
    """Build sample failed items for testing."""
    items = []
    for i in range(n):
        items.append(FailedItem(
            input_text=f"Test question {i+1}: What is topic {i+1}?",
            expected_output=f"A detailed answer about topic {i+1}",
            actual_output=f"Brief answer about topic {i+1}",
            score=0.3 + i * 0.1,
            rationale=f"Answer was too brief, missing key details about topic {i+1}",
        ))
    return items


def _mock_openai_response(improved_prompt: str, confidence: float = 0.85):
    """Create a mock OpenAI response with valid JSON."""
    resp_data = {
        "failure_analysis": "The agent was too brief in responses.",
        "changelog": [
            "Added instruction to provide detailed responses",
            "Added requirement to cite sources",
        ],
        "improved_prompt": improved_prompt,
        "confidence": confidence,
    }
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps(resp_data)))
    ]
    return mock_response


@pytest.mark.asyncio
async def test_rewrite_prompt_returns_improved_prompt():
    """should return an improved prompt with changelog when given failures"""
    original = "You are a helpful assistant."
    improved = "You are a helpful and detailed assistant. Always provide comprehensive answers."

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=_mock_openai_response(improved)
    )

    result = await rewrite_prompt(
        current_prompt=original,
        failed_items=_make_failed_items(),
        client=client,
    )

    assert isinstance(result, RewriteResult)
    assert result.original_prompt == original
    assert result.improved_prompt == improved
    assert result.confidence == 0.85
    assert len(result.changelog) == 2
    assert "detailed" in result.changelog[0].lower() or "instruction" in result.changelog[0].lower()


@pytest.mark.asyncio
async def test_rewrite_prompt_handles_json_parse_error():
    """should fallback gracefully when LLM returns invalid JSON"""
    client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="This is not JSON at all"))
    ]
    client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = await rewrite_prompt(
        current_prompt="You are helpful.",
        failed_items=_make_failed_items(1),
        client=client,
    )

    assert isinstance(result, RewriteResult)
    assert result.confidence == 0.2  # low confidence on parse error
    assert "not valid JSON" in result.changelog[0] or "raw text" in result.changelog[0]


@pytest.mark.asyncio
async def test_rewrite_prompt_handles_api_error():
    """should return original prompt with 0.0 confidence on API failure"""
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=Exception("API error"))

    result = await rewrite_prompt(
        current_prompt="You are helpful.",
        failed_items=_make_failed_items(1),
        client=client,
    )

    assert result.improved_prompt == "You are helpful."
    assert result.confidence == 0.0
    assert "failed" in result.changelog[0].lower() or "error" in result.changelog[0].lower()


@pytest.mark.asyncio
async def test_rewrite_prompt_limits_failures():
    """should only send max_failures items to the LLM"""
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=_mock_openai_response("improved prompt", 0.9)
    )

    await rewrite_prompt(
        current_prompt="test",
        failed_items=_make_failed_items(10),
        max_failures=3,
        client=client,
    )

    # Check the user content only includes 3 failures (the worst ones)
    call_args = client.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    user_content = messages[1]["content"]
    assert "FAILURE 1" in user_content
    assert "FAILURE 3" in user_content
    # Should not include FAILURE 4 through 10
    assert "FAILURE 4" not in user_content


@pytest.mark.asyncio
async def test_rewrite_prompt_sorts_by_worst_score():
    """should send worst-scoring items first"""
    items = [
        FailedItem("q1", "e1", "a1", 0.6, "almost"),
        FailedItem("q2", "e2", "a2", 0.1, "terrible"),
        FailedItem("q3", "e3", "a3", 0.3, "bad"),
    ]

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=_mock_openai_response("improved", 0.8)
    )

    await rewrite_prompt(
        current_prompt="test",
        failed_items=items,
        max_failures=2,
        client=client,
    )

    call_args = client.chat.completions.create.call_args
    user_content = call_args.kwargs["messages"][1]["content"]
    # The 0.1 score item should appear before 0.3
    pos_01 = user_content.find("score: 0.10")
    pos_03 = user_content.find("score: 0.30")
    assert pos_01 < pos_03, "Worst score should be FAILURE 1"


@pytest.mark.asyncio
async def test_rewrite_and_snapshot_creates_candidate_genome():
    """should create a CANDIDATE genome with the improved prompt"""
    agent_id = uuid4()
    workspace_id = uuid4()
    user_id = uuid4()

    pool = AsyncMock()
    conn = AsyncMock()

    # agent config fetch
    agent_row = {"config": {"system_prompt": "You are helpful."}}
    conn.fetchrow = AsyncMock(return_value=agent_row)
    conn.execute = AsyncMock()

    ctx_mgr = AsyncMock()
    ctx_mgr.__aenter__ = AsyncMock(return_value=conn)
    ctx_mgr.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=ctx_mgr)

    new_version_id = uuid4()

    with patch(
        "flow.application.prompt_rewriter.rewrite_prompt",
        return_value=RewriteResult(
            original_prompt="You are helpful.",
            improved_prompt="You are helpful. Always be detailed.",
            changelog=["Added detail instruction"],
            failure_analysis="Responses too brief",
            confidence=0.85,
        ),
    ), patch(
        "flow.application.genome_service.snapshot_genome",
        return_value=new_version_id,
    ) as mock_snap:
        result = await rewrite_and_snapshot(
            pool=pool,
            agent_id=agent_id,
            workspace_id=workspace_id,
            user_id=user_id,
            current_prompt="You are helpful.",
            failed_items=_make_failed_items(2),
            llm_config={"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.3},
        )

    assert result is not None
    assert result["candidate_version_id"] == str(new_version_id)
    assert result["rewrite"]["confidence"] == 0.85
    assert len(result["rewrite"]["changelog"]) == 1
    mock_snap.assert_called_once()
    # Check it was created as CANDIDATE
    from flow.domain.genome import VersionStatus
    assert mock_snap.call_args.kwargs["status"] == VersionStatus.CANDIDATE


@pytest.mark.asyncio
async def test_rewrite_and_snapshot_skips_on_low_confidence():
    """should return None when confidence is below threshold"""
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"config": {"system_prompt": "test"}})
    conn.execute = AsyncMock()
    ctx_mgr = AsyncMock()
    ctx_mgr.__aenter__ = AsyncMock(return_value=conn)
    ctx_mgr.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=ctx_mgr)

    with patch(
        "flow.application.prompt_rewriter.rewrite_prompt",
        return_value=RewriteResult(
            original_prompt="test",
            improved_prompt="test improved",
            changelog=["change"],
            failure_analysis="analysis",
            confidence=0.1,  # too low
        ),
    ):
        result = await rewrite_and_snapshot(
            pool=pool,
            agent_id=uuid4(),
            workspace_id=uuid4(),
            user_id=uuid4(),
            current_prompt="test",
            failed_items=_make_failed_items(1),
            llm_config={},
        )

    assert result is None


@pytest.mark.asyncio
async def test_rewrite_and_snapshot_skips_when_prompt_unchanged():
    """should return None when improved prompt equals original"""
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"config": {"system_prompt": "same prompt"}})
    conn.execute = AsyncMock()
    ctx_mgr = AsyncMock()
    ctx_mgr.__aenter__ = AsyncMock(return_value=conn)
    ctx_mgr.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=ctx_mgr)

    with patch(
        "flow.application.prompt_rewriter.rewrite_prompt",
        return_value=RewriteResult(
            original_prompt="same prompt",
            improved_prompt="same prompt",  # no change
            changelog=[],
            failure_analysis="",
            confidence=0.9,
        ),
    ):
        result = await rewrite_and_snapshot(
            pool=pool,
            agent_id=uuid4(),
            workspace_id=uuid4(),
            user_id=uuid4(),
            current_prompt="same prompt",
            failed_items=_make_failed_items(1),
            llm_config={},
        )

    assert result is None


@pytest.mark.asyncio
async def test_rewrite_and_snapshot_returns_none_for_empty_failures():
    """should return None when no failed items are provided"""
    result = await rewrite_and_snapshot(
        pool=AsyncMock(),
        agent_id=uuid4(),
        workspace_id=uuid4(),
        user_id=uuid4(),
        current_prompt="test",
        failed_items=[],
        llm_config={},
    )
    assert result is None


@pytest.mark.asyncio
async def test_rewrite_prompt_handles_markdown_wrapped_json():
    """should handle JSON wrapped in markdown code fences"""
    client = AsyncMock()
    resp_data = {
        "failure_analysis": "Too brief",
        "changelog": ["Fix 1"],
        "improved_prompt": "Better prompt",
        "confidence": 0.7,
    }
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=f"```json\n{json.dumps(resp_data)}\n```"))
    ]
    client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = await rewrite_prompt(
        current_prompt="test",
        failed_items=_make_failed_items(1),
        client=client,
    )

    assert result.improved_prompt == "Better prompt"
    assert result.confidence == 0.7
