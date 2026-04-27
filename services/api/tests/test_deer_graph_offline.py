from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from flow.infrastructure.graph.deer_graph import GraphContext, build_deer_flow_graph


def test_deer_graph_compiles_with_openai_disabled() -> None:
    """Graph builds with three nodes when no API key (offline / stub path in nodes)."""
    mock_pool = MagicMock()
    ctx = GraphContext(
        pool=mock_pool,
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        openai_api_key=None,
        agent_config={"tools": {"retrieve": False, "sandbox": False, "long_term_memory": False}},
    )
    compiled = build_deer_flow_graph(ctx, checkpointer=None)
    graph = compiled.get_graph()
    node_ids = set(graph.nodes)
    assert "planner" in node_ids
    assert "worker" in node_ids
    assert "synthesizer" in node_ids
