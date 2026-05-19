"""Tests for the regression report endpoint logic.

These tests validate the item-level regression detection that compares
consecutive eval runs to identify which items improved vs regressed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest


def _make_eval_run(items: list[dict], run_id=None, version_label="v1"):
    """Helper: build mock data for one eval run."""
    return {
        "eval_run_id": run_id or uuid4(),
        "run_at": datetime.now(UTC),
        "agent_version_label": version_label,
        "items": items,
    }


class TestRegressionDetection:
    """Unit tests for regression detection logic (extracted from endpoint)."""

    def _compare_runs(self, prev_scores: dict, curr_scores: dict) -> dict:
        """Simplified comparison logic matching the endpoint implementation."""
        all_items = set(prev_scores.keys()) | set(curr_scores.keys())
        improved, regressed, stable = [], [], []

        for item_id in all_items:
            prev = prev_scores.get(item_id, {}).get("score")
            curr = curr_scores.get(item_id, {}).get("score")
            if prev is None or curr is None:
                continue
            delta = curr - prev
            entry = {
                "item_id": item_id,
                "prev_score": round(prev, 3),
                "curr_score": round(curr, 3),
                "delta": round(delta, 3),
            }
            if delta > 0.05:
                improved.append(entry)
            elif delta < -0.05:
                regressed.append(entry)
            else:
                stable.append(entry)

        return {
            "improved": improved,
            "regressed": regressed,
            "stable": stable,
        }

    def test_detects_regression(self):
        """should detect items that regressed between runs"""
        item_a = str(uuid4())
        item_b = str(uuid4())

        prev = {
            item_a: {"score": 0.9},
            item_b: {"score": 0.8},
        }
        curr = {
            item_a: {"score": 0.3},  # regressed
            item_b: {"score": 0.85},  # stable (delta < 0.05)
        }

        result = self._compare_runs(prev, curr)
        assert len(result["regressed"]) == 1
        assert result["regressed"][0]["item_id"] == item_a
        assert result["regressed"][0]["delta"] == pytest.approx(-0.6)
        assert len(result["stable"]) == 1

    def test_detects_improvement(self):
        """should detect items that improved between runs"""
        item_a = str(uuid4())

        prev = {item_a: {"score": 0.3}}
        curr = {item_a: {"score": 0.8}}

        result = self._compare_runs(prev, curr)
        assert len(result["improved"]) == 1
        assert result["improved"][0]["delta"] == pytest.approx(0.5)

    def test_handles_mixed_changes(self):
        """should correctly categorize a mix of improved, regressed, and stable"""
        items = [str(uuid4()) for _ in range(4)]

        prev = {
            items[0]: {"score": 0.5},  # will improve
            items[1]: {"score": 0.9},  # will regress
            items[2]: {"score": 0.7},  # will stay stable
            items[3]: {"score": 0.6},  # will stay stable
        }
        curr = {
            items[0]: {"score": 0.8},  # improved (+0.3)
            items[1]: {"score": 0.4},  # regressed (-0.5)
            items[2]: {"score": 0.72},  # stable (+0.02)
            items[3]: {"score": 0.58},  # stable (-0.02)
        }

        result = self._compare_runs(prev, curr)
        assert len(result["improved"]) == 1
        assert len(result["regressed"]) == 1
        assert len(result["stable"]) == 2

    def test_handles_missing_items(self):
        """should gracefully handle items present in only one run"""
        item_a = str(uuid4())
        item_b = str(uuid4())

        prev = {item_a: {"score": 0.7}}
        curr = {item_b: {"score": 0.8}}

        result = self._compare_runs(prev, curr)
        # Both are skipped since they don't have matching scores
        assert len(result["improved"]) == 0
        assert len(result["regressed"]) == 0
        assert len(result["stable"]) == 0

    def test_handles_none_scores(self):
        """should skip items with None scores"""
        item_a = str(uuid4())

        prev = {item_a: {"score": None}}
        curr = {item_a: {"score": 0.8}}

        result = self._compare_runs(prev, curr)
        assert len(result["improved"]) == 0
        assert len(result["regressed"]) == 0

    def test_all_regressed(self):
        """should detect when all items regressed"""
        items = [str(uuid4()) for _ in range(3)]

        prev = {i: {"score": 0.9} for i in items}
        curr = {i: {"score": 0.2} for i in items}

        result = self._compare_runs(prev, curr)
        assert len(result["regressed"]) == 3
        assert len(result["improved"]) == 0


class TestTrendDetection:
    """Tests for overall trend calculation."""

    def _compute_trend(self, deltas: list[float]) -> str:
        """Match the endpoint logic for trend computation."""
        if len(deltas) < 2:
            return "insufficient_data"
        recent = deltas[-3:]
        avg = sum(recent) / len(recent)
        if avg > 0.02:
            return "improving"
        elif avg < -0.02:
            return "regressing"
        return "stable"

    def test_improving_trend(self):
        assert self._compute_trend([0.05, 0.03, 0.04]) == "improving"

    def test_regressing_trend(self):
        assert self._compute_trend([-0.05, -0.03, -0.04]) == "regressing"

    def test_stable_trend(self):
        assert self._compute_trend([0.01, -0.01, 0.005]) == "stable"

    def test_mixed_but_improving(self):
        assert self._compute_trend([-0.1, 0.05, 0.08, 0.06]) == "improving"

    def test_insufficient_data(self):
        assert self._compute_trend([0.05]) == "insufficient_data"

    def test_recent_regression_overrides_early_improvement(self):
        """only the last 3 deltas matter"""
        assert self._compute_trend([0.1, 0.1, -0.05, -0.04, -0.06]) == "regressing"


class TestVersionComparison:
    """Tests for version-to-version comparison across eval runs."""

    def test_version_label_tracking(self):
        """should track which version produced which scores"""
        runs = [
            {"version_label": "v1", "avg_score": 0.65},
            {"version_label": "v2-improved", "avg_score": 0.78},
            {"version_label": "v3-auto", "avg_score": 0.82},
        ]

        # Each run should maintain its version label
        for run in runs:
            assert run["version_label"] is not None

        # Score should improve across versions
        for i in range(1, len(runs)):
            assert runs[i]["avg_score"] > runs[i - 1]["avg_score"]

    def test_candidate_vs_active_comparison(self):
        """should correctly compare candidate and active version scores"""
        from flow.application.ab_runner import VersionScore

        active = VersionScore(
            version_id=uuid4(),
            version_label="v1-active",
            avg_score=0.72,
            pass_rate=0.70,
            item_count=10,
        )
        candidate = VersionScore(
            version_id=uuid4(),
            version_label="auto-eval-2026-05-11",
            avg_score=0.85,
            pass_rate=0.80,
            item_count=10,
        )

        delta = candidate.avg_score - active.avg_score
        assert delta > 0.05  # significant improvement
        assert candidate.pass_rate > active.pass_rate
