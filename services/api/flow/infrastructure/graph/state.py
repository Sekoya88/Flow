from __future__ import annotations

from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class FlowGraphState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]

    # linear-3 fields
    plan: str
    worker_output: str
    answer: str

    # researcher-critic-writer fields
    research_notes: str
    critique: str
    needs_more_research: bool
    research_iterations: int

    # curator / feedback fields
    confidence: float  # 0.0–1.0 self-assessed by synthesizer/writer

    # human-in-loop fields
    requires_approval: bool
    approved: bool
