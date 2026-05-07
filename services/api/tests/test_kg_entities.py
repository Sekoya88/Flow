from uuid import uuid4
from datetime import datetime, timezone


def test_kg_node_roundtrip():
    """should serialize and deserialize KGNode without data loss"""
    from flow.domain.knowledge_graph.entities import KGNode, NodeType

    node = KGNode(
        id=uuid4(),
        workspace_id=uuid4(),
        label="LangGraph",
        node_type=NodeType.NOTE,
        source_path="AI/LangGraph.md",
        content_hash="abc123",
        summary="Framework for stateful LLM agents",
        embedding=None,
        metadata={"tags": ["agents", "framework"]},
        cluster_id=1,
        pagerank=0.75,
        pos_x=100.0,
        pos_y=200.0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    data = node.model_dump()
    restored = KGNode(**data)
    assert restored.label == "LangGraph"
    assert restored.node_type == NodeType.NOTE
    assert restored.metadata["tags"] == ["agents", "framework"]


def test_edge_type_values():
    """should have correct string values for all EdgeType members"""
    from flow.domain.knowledge_graph.entities import EdgeType

    assert EdgeType.LINKS_TO == "links_to"
    assert EdgeType.TAGGED_WITH == "tagged_with"
    assert EdgeType.MENTIONS == "mentions"
    assert EdgeType.SIMILAR_TO == "similar_to"
    assert EdgeType.BELONGS_TO == "belongs_to"
    assert EdgeType.REFERENCED_BY == "referenced_by"
