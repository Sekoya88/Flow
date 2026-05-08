import pytest
from unittest.mock import MagicMock

from flow.infrastructure.llm.stub import StubChatModel


@pytest.mark.asyncio
async def test_extract_facts_returns_list():
    """should extract facts list when LLM returns valid JSON"""
    from flow.application.memory_judge import extract_facts_from_answer

    stub_llm = StubChatModel(responses=['["Fact A", "Fact B"]'])

    result = await extract_facts_from_answer(stub_llm, "What is X?", "X is Y and Z.")
    assert isinstance(result, list)
    assert len(result) == 2
    assert "Fact A" in result


@pytest.mark.asyncio
async def test_extract_facts_handles_bad_json():
    """should return empty list when LLM returns non-JSON"""
    from flow.application.memory_judge import extract_facts_from_answer

    stub_llm = StubChatModel(responses=["not json at all"])

    result = await extract_facts_from_answer(stub_llm, "Q", "A")
    assert result == []


@pytest.mark.asyncio
async def test_should_store_pattern_true_for_high_confidence():
    """should return True when confidence >= 0.8 and answer long enough"""
    from flow.application.memory_judge import should_store_pattern

    result = await should_store_pattern(confidence=0.85, answer_len=500)
    assert result is True


@pytest.mark.asyncio
async def test_should_store_pattern_false_for_low_confidence():
    """should return False when confidence < 0.8"""
    from flow.application.memory_judge import should_store_pattern

    result = await should_store_pattern(confidence=0.5, answer_len=500)
    assert result is False


@pytest.mark.asyncio
async def test_should_store_pattern_false_for_short_answer():
    """should return False when answer is too short (< 100 chars)"""
    from flow.application.memory_judge import should_store_pattern

    result = await should_store_pattern(confidence=0.9, answer_len=50)
    assert result is False
