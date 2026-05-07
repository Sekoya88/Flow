import pytest
import networkx as nx
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4


def _make_engine():
    from flow.infrastructure.kg.graph_engine import KGGraphEngine
    pool = MagicMock()
    return KGGraphEngine(pool)


def _make_graph():
    """Build a simple test graph: A → B → C, A → C"""
    G = nx.DiGraph()
    nodes = {name: str(uuid4()) for name in ["A", "B", "C", "D"]}
    for name, nid in nodes.items():
        G.add_node(nid, label=name, node_type="note", pagerank=0.0, cluster_id=0)
    G.add_edge(nodes["A"], nodes["B"], edge_type="links_to", weight=1.0)
    G.add_edge(nodes["B"], nodes["C"], edge_type="mentions", weight=0.8)
    G.add_edge(nodes["A"], nodes["C"], edge_type="links_to", weight=1.0)
    G.add_edge(nodes["C"], nodes["D"], edge_type="belongs_to", weight=0.7)
    return G, nodes


def test_find_shortest_path_direct():
    """should find path A→C directly"""
    engine = _make_engine()
    G, nodes = _make_graph()
    path = engine.find_shortest_path(G, "A", "C")
    assert path[0] == "A"
    assert path[-1] == "C"
    assert len(path) == 2  # direct edge A→C


def test_find_shortest_path_indirect():
    """should find path A→B→C when direct is absent"""
    engine = _make_engine()
    G, nodes = _make_graph()
    # Remove direct A→C edge
    G.remove_edge(nodes["A"], nodes["C"])
    path = engine.find_shortest_path(G, "A", "C")
    assert path == ["A", "B", "C"]


def test_find_path_raises_when_disconnected():
    """should raise NetworkXNoPath when nodes not connected"""
    import networkx as nx
    engine = _make_engine()
    G, nodes = _make_graph()
    # D has no path back to A (only incoming)
    with pytest.raises(nx.NetworkXNoPath):
        engine.find_shortest_path(G, "D", "A")


def test_get_subgraph_depth_1():
    """should return ego graph of radius 1 around B"""
    engine = _make_engine()
    G, nodes = _make_graph()
    sub = engine.get_subgraph(G, "B", depth=1)
    labels = {G.nodes[n]["label"] for n in sub.nodes}
    assert "B" in labels
    assert "A" in labels  # predecessor
    assert "C" in labels  # successor


def test_compute_metrics_adds_pagerank():
    """should add pagerank attribute to all nodes"""
    engine = _make_engine()
    G, nodes = _make_graph()
    engine.compute_metrics(G)
    for nid in G.nodes:
        assert G.nodes[nid]["pagerank"] > 0


def test_compute_metrics_assigns_clusters():
    """should assign cluster_id to all nodes"""
    engine = _make_engine()
    G, nodes = _make_graph()
    engine.compute_metrics(G)
    for nid in G.nodes:
        assert "cluster_id" in G.nodes[nid]
        assert isinstance(G.nodes[nid]["cluster_id"], int)


def test_spring_positions_are_in_range():
    """should return positions normalized to [0,1000] range"""
    engine = _make_engine()
    G, nodes = _make_graph()
    positions = engine.spring_positions(G)
    for nid, (x, y) in positions.items():
        assert 0 <= x <= 1000, f"x={x} out of range"
        assert 0 <= y <= 1000, f"y={y} out of range"
