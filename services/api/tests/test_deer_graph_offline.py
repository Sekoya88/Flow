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


def test_graph_context_has_store_field():
    """GraphContext accepts a store field."""
    from unittest.mock import MagicMock
    from uuid import uuid4

    from flow.infrastructure.graph.deer_graph import GraphContext

    ctx = GraphContext(
        pool=MagicMock(),
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        openai_api_key=None,
        agent_config={},
        store=MagicMock(),
    )
    assert ctx.store is not None


def test_react_agent_template_exists():
    """react-agent template is registered in TEMPLATES."""
    from flow.infrastructure.graph.spec import TEMPLATES

    assert "react-agent" in TEMPLATES
    spec = TEMPLATES["react-agent"]
    assert spec.template == "react-agent"
    assert spec.entry == "planner"


def test_should_retry_after_reflection_retries_on_low_grade():
    """Low grade + under retry cap -> loop back to worker."""
    from flow.infrastructure.graph.nodes import should_retry_after_reflection

    state = {"reflection": {"grade": 1}, "retry_count": 0}
    assert should_retry_after_reflection(state) == "worker"


def test_should_retry_after_reflection_stops_on_high_grade():
    """High grade -> terminate, no retry."""
    from flow.infrastructure.graph.nodes import should_retry_after_reflection

    state = {"reflection": {"grade": 5}, "retry_count": 0}
    assert should_retry_after_reflection(state) == "END"


def test_should_retry_after_reflection_stops_at_retry_cap():
    """Low grade but retry_count already at cap -> terminate (no infinite loop)."""
    from flow.infrastructure.graph.nodes import should_retry_after_reflection

    state = {"reflection": {"grade": 1}, "retry_count": 2}
    assert should_retry_after_reflection(state) == "END"


def test_linear3_and_deer_flow_wire_reflector_retry_loop():
    """linear-3 and deer_flow templates route reflector through the retry condition."""
    from flow.infrastructure.graph.spec import TEMPLATES

    for name in ("linear-3", "deer_flow"):
        spec = TEMPLATES[name]
        retry_edges = [e for e in spec.conditional_edges if e.source == "reflector"]
        assert retry_edges, f"{name}: no conditional edge from reflector"
        edge = retry_edges[0]
        assert edge.condition == "should_retry_after_reflection"
        assert edge.mapping.get("worker") == "worker"
        assert edge.mapping.get("END") == "END"
        assert ("reflector", "END") not in spec.edges
