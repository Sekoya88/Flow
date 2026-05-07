from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict
from uuid import UUID

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from flow.application.kg_parser import ObsidianDocument, ParsedNote, parse_obsidian_note
from flow.infrastructure.llm.embeddings import embed_texts


@dataclass
class IngestionConfig:
    workspace_id: UUID
    repo: Any          # FlowRepository — avoid circular import
    openai_api_key: str


class IngestionState(TypedDict):
    document: ObsidianDocument
    parsed: ParsedNote | None
    is_duplicate: bool
    entities: list[str]
    topic: str
    summary: str
    embedding: list[float]
    note_node_id: str | None
    error: str | None


def build_kg_ingestion_graph(config: IngestionConfig):
    """Build and compile the ingestion LangGraph. Returns a compiled graph."""

    repo = config.repo
    workspace_id = config.workspace_id
    api_key = config.openai_api_key

    def _llm() -> ChatOpenAI:
        return ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=api_key)

    # ── Node 1: parse ──────────────────────────────────────────────────────
    def parse_note(state: IngestionState) -> dict:
        parsed = parse_obsidian_note(state["document"])
        return {"parsed": parsed}

    # ── Node 2: duplicate check ────────────────────────────────────────────
    async def check_duplicate(state: IngestionState) -> dict:
        parsed = state["parsed"]
        existing = await repo.get_kg_node_by_label(workspace_id, parsed.title, "note")
        if existing and existing["content_hash"] == parsed.content_hash:
            return {"is_duplicate": True}
        return {"is_duplicate": False}

    def route_duplicate(state: IngestionState) -> str:
        return END if state["is_duplicate"] else "extract_entities"

    # ── Node 3: entity extraction ──────────────────────────────────────────
    async def extract_entities(state: IngestionState) -> dict:
        import json
        llm = _llm()
        parsed = state["parsed"]
        try:
            resp = await llm.ainvoke(
                f"""Extract up to 10 key concepts, people, technologies, or ideas from this text.
Return ONLY a JSON object: {{"entities": ["string", ...]}}

Text:
{parsed.body[:3000]}"""
            )
            data = json.loads(resp.content)
            entities = data.get("entities", [])[:10]
        except Exception:
            entities = []
        return {"entities": entities}

    # ── Node 4: topic assignment ───────────────────────────────────────────
    async def assign_topic(state: IngestionState) -> dict:
        import json
        llm = _llm()
        parsed = state["parsed"]
        existing_topics = await repo.list_kg_topics(workspace_id)
        topics_str = ", ".join(existing_topics) if existing_topics else "none yet"
        try:
            resp = await llm.ainvoke(
                f"""Assign one topic category to this note.
Prefer existing topics for consistency. Existing topics: {topics_str}
If none fit, create a short new one (2-3 words max).
Return ONLY: {{"topic": "string"}}

Note title: {parsed.title}
Note preview: {parsed.body[:800]}"""
            )
            data = json.loads(resp.content)
            topic = data.get("topic", "General")
        except Exception:
            topic = "General"
        return {"topic": topic}

    # ── Node 5: embed and summarize ────────────────────────────────────────
    async def embed_and_summarize(state: IngestionState) -> dict:
        llm = _llm()
        parsed = state["parsed"]
        text_to_embed = f"{parsed.title}\n\n{parsed.body[:2000]}"
        try:
            resp = await llm.ainvoke(
                f"Summarize in ≤200 characters:\n{parsed.body[:1500]}"
            )
            summary = resp.content[:200]
        except Exception:
            summary = parsed.title

        try:
            embeddings = await embed_texts(api_key=api_key, texts=[text_to_embed])
            embedding = embeddings[0]
        except Exception:
            embedding = []

        return {"summary": summary, "embedding": embedding}

    # ── Node 6: upsert nodes ───────────────────────────────────────────────
    async def upsert_nodes(state: IngestionState) -> dict:
        parsed = state["parsed"]

        # Upsert the note node
        note_id = await repo.upsert_kg_node(
            workspace_id=workspace_id,
            label=parsed.title,
            node_type="note",
            source_path=parsed.filename,
            content_hash=parsed.content_hash,
            summary=state["summary"],
            embedding=state["embedding"] or None,
            metadata={"tags": parsed.tags, "frontmatter": parsed.frontmatter},
        )

        # Upsert topic node
        await repo.upsert_kg_node(
            workspace_id=workspace_id,
            label=state["topic"],
            node_type="topic",
        )

        # Upsert concept nodes
        for entity in state["entities"]:
            await repo.upsert_kg_node(
                workspace_id=workspace_id,
                label=entity,
                node_type="concept",
            )

        return {"note_node_id": str(note_id)}

    # ── Node 7: build edges ────────────────────────────────────────────────
    async def build_edges(state: IngestionState) -> dict:
        parsed = state["parsed"]
        note_id_str = state["note_node_id"]
        if not note_id_str:
            return {}
        note_id = UUID(note_id_str)

        # note → topic
        topic_node = await repo.get_kg_node_by_label(workspace_id, state["topic"], "topic")
        if topic_node:
            await repo.upsert_kg_edge(workspace_id, note_id, topic_node["id"], "belongs_to", 1.0)

        # note → entities
        for entity in state["entities"]:
            concept_node = await repo.get_kg_node_by_label(workspace_id, entity, "concept")
            if concept_node:
                await repo.upsert_kg_edge(workspace_id, note_id, concept_node["id"], "mentions", 0.8)

        # note → wikilinks
        for wikilink in parsed.wikilinks:
            linked_node = await repo.get_kg_node_by_label(workspace_id, wikilink, "note")
            if linked_node:
                await repo.upsert_kg_edge(workspace_id, note_id, linked_node["id"], "links_to", 1.0)

        # note → tags
        for tag in parsed.tags:
            tag_node = await repo.get_kg_node_by_label(workspace_id, tag, "topic")
            if tag_node:
                await repo.upsert_kg_edge(workspace_id, note_id, tag_node["id"], "tagged_with", 0.7)

        # similar_to: vector search top-5 excluding self
        if state["embedding"]:
            similar = await repo.vector_search_kg(workspace_id, state["embedding"], k=6)
            for row in similar:
                if str(row["id"]) == note_id_str:
                    continue
                dist = float(row["dist"])
                if dist < 0.15:  # similarity > 0.85
                    await repo.upsert_kg_edge(
                        workspace_id, note_id, row["id"], "similar_to", 1.0 - dist
                    )

        return {}

    # ── Build graph ─────────────────────────────────────────────────────────
    builder = StateGraph(IngestionState)
    builder.add_node("parse_note", parse_note)
    builder.add_node("check_duplicate", check_duplicate)
    builder.add_node("extract_entities", extract_entities)
    builder.add_node("assign_topic", assign_topic)
    builder.add_node("embed_and_summarize", embed_and_summarize)
    builder.add_node("upsert_nodes", upsert_nodes)
    builder.add_node("build_edges", build_edges)

    builder.set_entry_point("parse_note")
    builder.add_edge("parse_note", "check_duplicate")
    builder.add_conditional_edges("check_duplicate", route_duplicate, {"extract_entities": "extract_entities", END: END})
    builder.add_edge("extract_entities", "assign_topic")
    builder.add_edge("assign_topic", "embed_and_summarize")
    builder.add_edge("embed_and_summarize", "upsert_nodes")
    builder.add_edge("upsert_nodes", "build_edges")
    builder.add_edge("build_edges", END)

    return builder.compile()
