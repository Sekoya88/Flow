"""Smoke tests: TypedDicts are importable and have expected keys."""

import typing


def test_digest_run_record_keys():
    from flow.infrastructure.persistence.record_types import DigestRunRecord

    hints = typing.get_type_hints(DigestRunRecord)
    assert "id" in hints
    assert "workspace_id" in hints
    assert "status" in hints
    assert "paper_count" in hints


def test_digest_paper_record_keys():
    from flow.infrastructure.persistence.record_types import DigestPaperRecord

    hints = typing.get_type_hints(DigestPaperRecord)
    assert "id" in hints
    assert "title" in hints
    assert "obsidian_path" in hints
    assert "digest_run_id" in hints


def test_training_run_record_keys():
    from flow.infrastructure.persistence.record_types import TrainingRunRecord

    hints = typing.get_type_hints(TrainingRunRecord)
    assert "skill_id" in hints
    assert "best_score" in hints
    assert "status" in hints
    assert "skill_name" in hints
