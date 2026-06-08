import pytest

from flow.application.golden_generator import GeneratedItem, build_generation_prompt, parse_generation_response


def test_build_prompt_includes_skill_body_and_count():
    prompt = build_generation_prompt(skill_name="web-research", skill_body="Do research.", n=4)
    assert "web-research" in prompt
    assert "Do research." in prompt
    assert "4" in prompt


def test_parse_response_extracts_items():
    raw = """```json
    {"items": [
      {"input_text": "Q1", "expected_output": "A1", "scoring_criteria": "must cite", "rationale": "tests citing"}
    ]}
    ```"""
    items = parse_generation_response(raw)
    assert len(items) == 1
    assert isinstance(items[0], GeneratedItem)
    assert items[0].input_text == "Q1"
    assert items[0].scoring_criteria == "must cite"


def test_parse_response_tolerates_garbage():
    assert parse_generation_response("not json") == []
