"""Tests for CV → preference mapping and Deep Agent payload parsing."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from flow.domain.preferences.cv_mapping import shards_to_preference_rows
from flow.domain.preferences.cv_schemas import NarrativeCvShard, ToolingCvShard, VetoChannelCvShard
from flow.infrastructure.llm.cv_profile_deep_agent import parse_subagent_tool_payloads


def test_shards_to_preference_rows_dedup_and_classes() -> None:
    t = ToolingCvShard(items=["Python", "python", "Go"], notes=None)
    n = NarrativeCvShard(
        domains=["FinTech"],
        goals=["Ship APIs"],
        style_hints=["Concise"],
    )
    v = VetoChannelCvShard(vetoes=["PHP"], channels=["Syntax-highlighted blocks"])
    rows = shards_to_preference_rows(t, n, v)
    classes = {r["class"] for r in rows}
    assert classes <= {"tooling", "domain", "goal", "style", "veto", "channel"}
    assert sum(1 for r in rows if r["class"] == "tooling") == 2  # python deduped
    assert any(r == {"class": "domain", "value": "FinTech"} for r in rows)


def test_parse_subagent_tool_payloads_reads_task_json() -> None:
    msgs = [
        HumanMessage(content="x"),
        ToolMessage(
            content=json.dumps({"items": ["Rust"], "notes": None}),
            tool_call_id="1",
            name="task",
        ),
        ToolMessage(
            content=json.dumps(
                {
                    "domains": ["Security"],
                    "goals": [],
                    "style_hints": ["Verbose"],
                }
            ),
            tool_call_id="2",
            name="task",
        ),
        ToolMessage(
            content=json.dumps({"vetoes": [], "channels": ["Inline snippets"]}),
            tool_call_id="3",
            name="task",
        ),
    ]
    tooling, narrative, veto = parse_subagent_tool_payloads(msgs)
    assert tooling is not None and tooling.items == ["Rust"]
    assert narrative is not None and narrative.domains == ["Security"]
    assert veto is not None and veto.channels == ["Inline snippets"]


def test_parse_ignores_non_task_messages() -> None:
    msgs = [AIMessage(content="ok"), ToolMessage(content="not-json", tool_call_id="1", name="other")]
    assert parse_subagent_tool_payloads(msgs) == (None, None, None)
