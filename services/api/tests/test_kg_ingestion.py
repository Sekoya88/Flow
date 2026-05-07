import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


@pytest.mark.asyncio
async def test_full_ingestion_creates_note_node():
    """should upsert a NOTE node after ingesting a document"""
    from flow.application.kg_ingestion_graph import build_kg_ingestion_graph, IngestionConfig
    from flow.application.kg_parser import ObsidianDocument

    workspace_id = uuid4()
    node_id = uuid4()

    mock_repo = AsyncMock()
    mock_repo.get_kg_node_by_label.return_value = None   # not duplicate
    mock_repo.upsert_kg_node.return_value = node_id
    mock_repo.upsert_kg_edge.return_value = uuid4()
    mock_repo.list_kg_topics.return_value = ["AI", "Engineering"]
    mock_repo.vector_search_kg.return_value = []

    mock_llm = AsyncMock()
    # extract_entities response
    mock_llm.ainvoke.side_effect = [
        MagicMock(content='{"entities": ["LangGraph", "agents"]}'),
        MagicMock(content='{"topic": "AI"}'),
        MagicMock(content="A note about LangGraph framework."),
    ]

    with patch("flow.application.kg_ingestion_graph.ChatOpenAI", return_value=mock_llm), \
         patch("flow.application.kg_ingestion_graph.embed_texts", new_callable=AsyncMock) as mock_emb:
        mock_emb.return_value = [[0.1] * 1536]

        config = IngestionConfig(
            workspace_id=workspace_id,
            repo=mock_repo,
            openai_api_key="sk-test",
        )
        graph = build_kg_ingestion_graph(config)
        doc = ObsidianDocument(
            filename="AI/LangGraph.md",
            raw_content="# LangGraph\nA stateful agent framework. #agents [[RAG]]",
            source="upload",
        )
        result = await graph.ainvoke({"document": doc})

    assert result.get("note_node_id") is not None
    assert mock_repo.upsert_kg_node.called


@pytest.mark.asyncio
async def test_duplicate_detection_skips_processing():
    """should skip extraction when content_hash already exists"""
    from flow.application.kg_ingestion_graph import build_kg_ingestion_graph, IngestionConfig
    from flow.application.kg_parser import ObsidianDocument
    import hashlib

    workspace_id = uuid4()
    content = "# Test\nSame content"
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    mock_repo = AsyncMock()
    mock_repo.get_kg_node_by_label.return_value = {"content_hash": content_hash}

    config = IngestionConfig(workspace_id=workspace_id, repo=mock_repo, openai_api_key="sk-test")
    graph = build_kg_ingestion_graph(config)
    doc = ObsidianDocument(filename="test.md", raw_content=content, source="upload")
    result = await graph.ainvoke({"document": doc})

    assert result["is_duplicate"] is True
    assert mock_repo.upsert_kg_node.call_count == 0
