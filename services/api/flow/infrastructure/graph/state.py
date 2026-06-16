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
    rag_sources: list[dict]  # [{"source_id": str, "title": str, "chunk_index": int, "preview": str}]
    reflection: dict  # added for reflector node output
    prediction: str  # JEPA-style: reflector predicts next likely query/topic
    retry_count: int  # bounded self-correction loop: reflector -> worker retries

    # Phase 1 — Skills Loader
    active_skills: list[dict]  # matched skills for this execution (serialized MatchedSkill)

    # Phase 2 — MetaCognition
    metacog_state: dict  # accumulated metacognitive context (calibration, journal entries)
