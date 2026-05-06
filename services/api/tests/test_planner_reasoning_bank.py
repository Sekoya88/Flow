import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


@pytest.mark.asyncio
async def test_planner_queries_reasoning_bank():
    """should call search_reasoning_patterns when openai_api_key is set"""
    from flow.infrastructure.graph.deer_graph import GraphContext

    ctx = GraphContext(
        pool=AsyncMock(),
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        openai_api_key="sk-test",
        agent_config={},
    )

    mock_pattern = {
        "id": uuid4(),
        "problem_summary": "Research query about ML",
        "solution_steps": "1. Search\n2. Summarize",
        "score": 0.9,
        "use_count": 2,
    }

    from flow.infrastructure.graph.nodes import make_planner  # ensure module is loaded

    with (
        patch("flow.infrastructure.persistence.repo.FlowRepository") as MockRepo,
        patch("flow.infrastructure.llm.embeddings.embed_texts", new_callable=AsyncMock) as mock_emb,
        patch("flow.infrastructure.graph.nodes._get_llm", return_value=None),
    ):
        mock_repo_inst = AsyncMock()
        mock_repo_inst.search_reasoning_patterns.return_value = [mock_pattern]
        MockRepo.return_value = mock_repo_inst
        mock_emb.return_value = [[0.1] * 1536]

        planner_fn = make_planner(ctx)
        state = {"messages": [MagicMock(type="human", content="How does ML work?")]}
        result = await planner_fn(state)

        assert "plan" in result
        mock_repo_inst.search_reasoning_patterns.assert_called_once()


@pytest.mark.asyncio
async def test_planner_skips_bank_without_api_key():
    """should skip ReasoningBank query when no openai_api_key"""
    from flow.infrastructure.graph.deer_graph import GraphContext

    ctx = GraphContext(
        pool=AsyncMock(),
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        openai_api_key=None,
        agent_config={},
    )

    from flow.infrastructure.graph.nodes import make_planner  # ensure module is loaded

    with (
        patch("flow.infrastructure.persistence.repo.FlowRepository") as MockRepo,
        patch("flow.infrastructure.graph.nodes._get_llm", return_value=None),
    ):
        mock_repo_inst = AsyncMock()
        MockRepo.return_value = mock_repo_inst

        planner_fn = make_planner(ctx)
        state = {"messages": [MagicMock(type="human", content="Hello")]}
        result = await planner_fn(state)

        assert "plan" in result
        mock_repo_inst.search_reasoning_patterns.assert_not_called()
