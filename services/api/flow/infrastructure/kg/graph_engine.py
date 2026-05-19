from __future__ import annotations

from uuid import UUID

import networkx as nx


class KGGraphEngine:
    def __init__(self, pool) -> None:
        self._pool = pool

    async def load_graph(self, workspace_id: UUID) -> nx.DiGraph:
        """Load full workspace graph from Postgres into NetworkX DiGraph."""
        nodes = await self._pool.fetch(
            "SELECT id, label, node_type, pagerank, cluster_id FROM kg_nodes WHERE workspace_id=$1",
            workspace_id,
        )
        edges = await self._pool.fetch(
            "SELECT source_id, target_id, edge_type, weight FROM kg_edges WHERE workspace_id=$1",
            workspace_id,
        )
        G: nx.DiGraph = nx.DiGraph()
        for n in nodes:
            G.add_node(
                str(n["id"]),
                label=n["label"],
                node_type=n["node_type"],
                pagerank=float(n["pagerank"]),
                cluster_id=n["cluster_id"],
            )
        for e in edges:
            G.add_edge(
                str(e["source_id"]),
                str(e["target_id"]),
                edge_type=e["edge_type"],
                weight=float(e["weight"]),
            )
        return G

    def find_shortest_path(self, G: nx.DiGraph, source_label: str, target_label: str) -> list[str]:
        """Return list of node labels on the shortest path. Raises nx.NetworkXNoPath if none."""
        label_to_id = {data["label"]: nid for nid, data in G.nodes(data=True)}
        src = label_to_id.get(source_label)
        tgt = label_to_id.get(target_label)
        if src is None or tgt is None:
            raise nx.NetworkXNoPath(f"Node not found: {source_label!r} or {target_label!r}")
        id_path = nx.shortest_path(G, src, tgt)
        return [G.nodes[nid]["label"] for nid in id_path]

    def find_shortest_path_ids(
        self, G: nx.DiGraph, source_label: str, target_label: str
    ) -> tuple[list[str], list[str]]:
        """Return (label_path, edge_types) for the shortest path."""
        label_to_id = {data["label"]: nid for nid, data in G.nodes(data=True)}
        src = label_to_id.get(source_label)
        tgt = label_to_id.get(target_label)
        if src is None or tgt is None:
            raise nx.NetworkXNoPath("Node not found")
        id_path = nx.shortest_path(G, src, tgt)
        labels = [G.nodes[nid]["label"] for nid in id_path]
        edge_types: list[str] = []
        for a, b in zip(id_path, id_path[1:], strict=False):
            edge_types.append(G.edges[a, b].get("edge_type", "links_to"))
        return labels, edge_types

    def get_subgraph(self, G: nx.DiGraph, center_label: str, depth: int = 2) -> nx.DiGraph:
        """BFS ego graph of radius=depth around center node (undirected for traversal)."""
        label_to_id = {data["label"]: nid for nid, data in G.nodes(data=True)}
        center_id = label_to_id.get(center_label)
        if center_id is None:
            return nx.DiGraph()
        undirected = G.to_undirected()
        ego = nx.ego_graph(undirected, center_id, radius=depth)
        return G.subgraph(ego.nodes).copy()

    def get_cluster_nodes(self, G: nx.DiGraph, cluster_id: int) -> list[dict]:
        """All nodes in a Louvain cluster, sorted by pagerank desc."""
        result = [
            {"label": data["label"], "pagerank": data.get("pagerank", 0.0), "node_type": data.get("node_type")}
            for nid, data in G.nodes(data=True)
            if data.get("cluster_id") == cluster_id
        ]
        return sorted(result, key=lambda x: x["pagerank"], reverse=True)

    def compute_metrics(self, G: nx.DiGraph) -> None:
        """Compute PageRank and Louvain clusters in-place on G."""
        if G.number_of_nodes() == 0:
            return
        try:
            pr = nx.pagerank(G, alpha=0.85)
        except ModuleNotFoundError:
            # scipy not available; fall back to pure-python implementation
            from networkx.algorithms.link_analysis.pagerank_alg import _pagerank_python
            pr = _pagerank_python(G, alpha=0.85)
        for nid, score in pr.items():
            G.nodes[nid]["pagerank"] = score

        try:
            import community as community_louvain
            undirected = G.to_undirected()
            partition = community_louvain.best_partition(undirected)
            for nid, cluster in partition.items():
                G.nodes[nid]["cluster_id"] = cluster
        except ImportError:
            # Fallback: assign all to cluster 0
            for nid in G.nodes:
                G.nodes[nid]["cluster_id"] = 0

    def spring_positions(self, G: nx.DiGraph, scale: float = 1000.0) -> dict[str, tuple[float, float]]:
        """Compute Fruchterman-Reingold spring positions, scaled to [0, scale]."""
        if G.number_of_nodes() == 0:
            return {}
        pos = nx.spring_layout(G, seed=42, k=2.0 / (G.number_of_nodes() ** 0.5 + 1))
        # pos values are in [-1, 1]; shift and scale to [0, scale]
        result: dict[str, tuple[float, float]] = {}
        for nid, (x, y) in pos.items():
            result[nid] = ((x + 1) / 2 * scale, (y + 1) / 2 * scale)
        return result
