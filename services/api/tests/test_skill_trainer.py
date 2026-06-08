"""Tests for skill_trainer.py — ReflACT pipeline unit tests.

Covers pure (no-IO) stages: aggregate, select, update.
"""

from __future__ import annotations

from flow.application.skill_trainer import RawPatch, SkillTrainer

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _trainer() -> SkillTrainer:
    """SkillTrainer with a None pool (only pure methods tested)."""
    return SkillTrainer(pool=None)  # type: ignore[arg-type]


_SKILL_BODY = """\
## Instructions
Follow these steps carefully.

## Output Format
Return a JSON object.

## Examples
Here is an example.
"""


# ── _stage_aggregate ─────────────────────────────────────────────────────────


def test_stage_aggregate_keeps_higher_impact_score_per_target():
    trainer = _trainer()
    patches = [
        RawPatch(op="replace", target="## Instructions", content="First", impact_score=0.5),
        RawPatch(op="append", target="## Instructions", content="Second", impact_score=0.9),
        RawPatch(op="replace", target="## Output Format", content="Only one", impact_score=0.7),
    ]
    result = trainer._stage_aggregate(patches)

    # Two unique targets → two patches
    assert len(result) == 2

    # The Instructions patch kept should be the one with impact_score=0.9
    instr_patch = next(p for p in result if p.target == "## Instructions")
    assert instr_patch.impact_score == 0.9
    assert instr_patch.content == "Second"


def test_stage_aggregate_single_patch_per_target_unchanged():
    trainer = _trainer()
    patches = [
        RawPatch(op="replace", target="## Output Format", content="JSON only", impact_score=0.8),
    ]
    result = trainer._stage_aggregate(patches)
    assert len(result) == 1
    assert result[0].content == "JSON only"


def test_stage_aggregate_empty_input_returns_empty():
    trainer = _trainer()
    assert trainer._stage_aggregate([]) == []


# ── _stage_select ─────────────────────────────────────────────────────────────


def test_stage_select_returns_top_n_by_impact_score():
    trainer = _trainer()
    patches = [RawPatch(op="append", target=f"## Section{i}", content=f"c{i}", impact_score=float(i) / 10) for i in range(6)]
    # Budget = 3 → top 3 should be indices 5, 4, 3 (scores 0.5, 0.4, 0.3)
    result = trainer._stage_select(patches, budget=3)
    assert len(result) == 3
    scores = [p.impact_score for p in result]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 0.5


def test_stage_select_budget_larger_than_list_returns_all():
    trainer = _trainer()
    patches = [
        RawPatch(op="replace", target="## A", content="x", impact_score=0.7),
        RawPatch(op="append", target="## B", content="y", impact_score=0.3),
    ]
    result = trainer._stage_select(patches, budget=10)
    assert len(result) == 2


def test_stage_select_empty_input_returns_empty():
    trainer = _trainer()
    assert trainer._stage_select([], budget=3) == []


# ── _stage_update: replace ────────────────────────────────────────────────────


def test_stage_update_replace_substitutes_section_content():
    trainer = _trainer()
    patch = RawPatch(op="replace", target="## Output Format", content="Return plain text.", impact_score=0.8)
    result = trainer._stage_update(_SKILL_BODY, [patch])

    assert "Return plain text." in result
    assert "Return a JSON object." not in result
    # Other sections preserved
    assert "## Instructions" in result
    assert "## Examples" in result


def test_stage_update_replace_last_section():
    """Replace works even when the target is the last section (no next heading)."""
    trainer = _trainer()
    patch = RawPatch(op="replace", target="## Examples", content="No examples needed.", impact_score=0.6)
    result = trainer._stage_update(_SKILL_BODY, [patch])

    assert "No examples needed." in result
    assert "Here is an example." not in result


# ── _stage_update: append ─────────────────────────────────────────────────────


def test_stage_update_append_adds_content_within_section():
    trainer = _trainer()
    patch = RawPatch(op="append", target="## Instructions", content="Always be concise.", impact_score=0.7)
    result = trainer._stage_update(_SKILL_BODY, [patch])

    assert "Always be concise." in result
    # Original content preserved
    assert "Follow these steps carefully." in result
    # The appended content should appear before the next section heading
    instructions_pos = result.index("Always be concise.")
    next_section_pos = result.index("## Output Format")
    assert instructions_pos < next_section_pos


# ── _stage_update: heading not found ─────────────────────────────────────────


def test_stage_update_append_heading_not_found_appends_new_section():
    trainer = _trainer()
    patch = RawPatch(op="append", target="## Constraints", content="Max 200 words.", impact_score=0.9)
    result = trainer._stage_update(_SKILL_BODY, [patch])

    assert "## Constraints" in result
    assert "Max 200 words." in result
    # Original content still present
    assert "## Instructions" in result


def test_stage_update_replace_heading_not_found_appends_new_section():
    trainer = _trainer()
    patch = RawPatch(op="replace", target="## NonExistent", content="New content here.", impact_score=0.5)
    result = trainer._stage_update(_SKILL_BODY, [patch])

    assert "## NonExistent" in result
    assert "New content here." in result
    # Original sections untouched
    assert "## Instructions" in result
    assert "## Output Format" in result


# ── _stage_update: insert ─────────────────────────────────────────────────────


def test_stage_update_insert_places_content_before_heading():
    trainer = _trainer()
    patch = RawPatch(op="insert", target="## Output Format", content="<!-- NOTE: format spec below -->", impact_score=0.6)
    result = trainer._stage_update(_SKILL_BODY, [patch])

    assert "<!-- NOTE: format spec below -->" in result
    note_pos = result.index("<!-- NOTE: format spec below -->")
    format_pos = result.index("## Output Format")
    assert note_pos < format_pos


# ── _stage_update: delete ─────────────────────────────────────────────────────


def test_stage_update_delete_removes_section():
    trainer = _trainer()
    patch = RawPatch(op="delete", target="## Examples", content="", impact_score=0.4)
    result = trainer._stage_update(_SKILL_BODY, [patch])

    assert "## Examples" not in result
    assert "Here is an example." not in result
    # Other sections intact
    assert "## Instructions" in result
    assert "## Output Format" in result


# ── _stage_update: protected sections ────────────────────────────────────────


def test_stage_update_skips_protected_slow_update_sections():
    trainer = _trainer()
    body_with_protected = """\
## Instructions
Do something.

<!-- SLOW_UPDATE_START -->
## Protected Section
This must not change.
<!-- SLOW_UPDATE_END -->

## Output Format
Return JSON.
"""
    patch = RawPatch(op="replace", target="## Protected Section", content="Changed!", impact_score=1.0)
    result = trainer._stage_update(body_with_protected, [patch])

    # Content should be unchanged
    assert "This must not change." in result
    assert "Changed!" not in result


# ── Multiple patches in one epoch ─────────────────────────────────────────────


def test_stage_update_applies_multiple_patches_sequentially():
    trainer = _trainer()
    patches = [
        RawPatch(op="replace", target="## Instructions", content="Be precise and brief.", impact_score=0.9),
        RawPatch(op="append", target="## Output Format", content="Include a summary field.", impact_score=0.7),
    ]
    result = trainer._stage_update(_SKILL_BODY, patches)

    assert "Be precise and brief." in result
    assert "Follow these steps carefully." not in result
    assert "Include a summary field." in result
    assert "Return a JSON object." in result  # original content still there (append, not replace)
