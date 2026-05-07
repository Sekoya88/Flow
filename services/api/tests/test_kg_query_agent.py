import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


@pytest.mark.asyncio
async def test_query_agent_returns_answer():
    """should produce an answer string from a factual question"""
    from flow.application.kg_query_graph import build_kg_query_graph, QueryConfig

    workspace_id = uuid4()
    mock_repo = AsyncMock()
    mock_repo.vector_search_kg.return_value = [
        {"id": uuid4(), "label": "LangGraph", "summary": "Stateful LLM framework", "node_type": "note", "source_path": "AI/LangGraph.md", "dist": 0.1}
    ]
    mock_repo.get_kg_node.return_value = {"id": uuid4(), "label": "LangGraph", "metadata": {"tags": []}, "source_path": "AI/LangGraph.md"}

    mock_engine = MagicMock()
    mock_engine.find_shortest_path_ids.side_effect = Exception("not used")

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="LangGraph is a framework for building stateful LLM agents.")

    with patch("flow.application.kg_query_graph.ChatOpenAI", return_value=mock_llm), \
         patch("flow.application.kg_query_graph.embed_texts", new_callable=AsyncMock) as mock_emb:
        mock_emb.return_value = [[0.1] * 1536]
        config = QueryConfig(workspace_id=workspace_id, repo=mock_repo, engine=mock_engine, openai_api_key="sk-test")
        graph = build_kg_query_graph(config)
        result = await graph.ainvoke({"question": "What is LangGraph?"})

    assert result.get("answer") is not None
    assert len(result["answer"]) > 0


@pytest.mark.asyncio
async def test_query_agent_records_tool_calls():
    """should record tool_calls for frontend tracing"""
    from flow.application.kg_query_graph import build_kg_query_graph, QueryConfig

    workspace_id = uuid4()
    mock_repo = AsyncMock()
    mock_repo.vector_search_kg.return_value = []
    mock_engine = MagicMock()

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(content="No relevant notes found.")

    with patch("flow.application.kg_query_graph.ChatOpenAI", return_value=mock_llm), \
         patch("flow.application.kg_query_graph.embed_texts", new_callable=AsyncMock) as mock_emb:
        mock_emb.return_value = [[0.1] * 1536]
        config = QueryConfig(workspace_id=workspace_id, repo=mock_repo, engine=mock_engine, openai_api_key="sk-test")
        graph = build_kg_query_graph(config)
        result = await graph.ainvoke({"question": "What do I know about transformers?"})

    assert "tool_calls" in result
    assert isinstance(result["tool_calls"], list)
