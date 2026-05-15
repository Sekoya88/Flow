from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flow.application.preference_service import (
    effective_score,
    auto_graduate,
    extract_preferences,
    extract_preferences_from_cv,
    process_onboarding_answers,
)


def dt(days_ago: int) -> datetime:
    return datetime.now(tz=timezone.utc) - timedelta(days=days_ago)


class TestEffectiveScore:
    def test_no_decay_when_fresh(self):
        score = effective_score(0.8, dt(0), 30)
        assert abs(score - 0.8) < 0.01

    def test_half_at_half_life(self):
        score = effective_score(1.0, dt(30), 30)
        assert abs(score - 0.5) < 0.01

    def test_pinned_skips_decay(self):
        score = effective_score(0.8, dt(300), 30, pinned=True)
        assert score == 0.8

    def test_zero_after_many_half_lives(self):
        score = effective_score(0.5, dt(200), 30)
        assert score < 0.1


class TestAutoGraduate:
    def test_candidate_to_provisional_at_07(self):
        row = {"status": "candidate", "score": 0.71, "last_reinforced_at": dt(0), "decay_half_life_days": 30, "pinned": False}
        assert auto_graduate(row) == "provisional"

    def test_candidate_stays_candidate_below_07(self):
        row = {"status": "candidate", "score": 0.65, "last_reinforced_at": dt(0), "decay_half_life_days": 30, "pinned": False}
        assert auto_graduate(row) is None

    def test_provisional_to_active_at_09(self):
        row = {"status": "provisional", "score": 0.91, "last_reinforced_at": dt(0), "decay_half_life_days": 30, "pinned": False}
        assert auto_graduate(row) == "active"

    def test_active_stays_active(self):
        row = {"status": "active", "score": 1.0, "last_reinforced_at": dt(0), "decay_half_life_days": 30, "pinned": False}
        assert auto_graduate(row) is None


class TestExtractPreferences:
    @pytest.mark.asyncio
    async def test_returns_list_of_class_value_dicts(self):
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content='[{"class": "tooling", "value": "uses Python"}]'
        )
        result = await extract_preferences(llm, "Q: use python. A: here is python code")
        assert result == [{"class": "tooling", "value": "uses Python"}]

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_preferences(self):
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="[]")
        result = await extract_preferences(llm, "Hello world")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_invalid_json(self):
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="not json")
        result = await extract_preferences(llm, "some text")
        assert result == []

    @pytest.mark.asyncio
    async def test_filters_invalid_class(self):
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content='[{"class": "invalid_class", "value": "something"}, {"class": "style", "value": "concise"}]'
        )
        result = await extract_preferences(llm, "text")
        assert len(result) == 1
        assert result[0]["class"] == "style"


class TestExtractPreferencesFromCV:
    @pytest.mark.asyncio
    async def test_truncates_text_to_8000_chars(self):
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="[]")
        long_text = "x" * 10000
        await extract_preferences_from_cv(llm, long_text)
        call_content = llm.ainvoke.call_args[0][0]
        # The prompt contains the truncated text
        truncated_in_prompt = "x" * 8000 in str(call_content)
        assert truncated_in_prompt
        assert "x" * 8001 not in str(call_content)

    @pytest.mark.asyncio
    async def test_returns_extracted_items(self):
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content='[{"class": "domain", "value": "works in fintech"}, {"class": "tooling", "value": "uses Python"}]'
        )
        result = await extract_preferences_from_cv(llm, "resume text")
        assert len(result) == 2
        assert {"class": "domain", "value": "works in fintech"} in result


class TestProcessOnboardingAnswers:
    def test_returns_active_preferences(self):
        answers = [
            {"class": "tooling", "value": "Python"},
            {"class": "domain", "value": "fintech"},
        ]
        result = process_onboarding_answers(answers)
        assert all(r["status"] == "active" for r in result)
        assert len(result) == 2

    def test_filters_empty_values(self):
        answers = [
            {"class": "tooling", "value": "Python"},
            {"class": "style", "value": ""},
        ]
        result = process_onboarding_answers(answers)
        assert len(result) == 1

    def test_filters_invalid_class(self):
        answers = [
            {"class": "unknown", "value": "something"},
            {"class": "goal", "value": "build a SaaS"},
        ]
        result = process_onboarding_answers(answers)
        assert len(result) == 1
        assert result[0]["class"] == "goal"
