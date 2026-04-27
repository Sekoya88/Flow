"""JSON → LangGraph StateGraph compiler.

GraphSpec describes nodes + edges as data. Templates ship as dicts stored in
agents.config["graph"]. The compiler wires them into a StateGraph at execution
time so new topologies need no code deploys — only an agent config update.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from flow.infrastructure.graph.state import FlowGraphState


@dataclass
class ConditionalEdge:
    source: str
    condition: str  # key in condition_registry
    # maps condition return value → node name or END
    mapping: dict[str, str]


@dataclass
class GraphSpec:
    template: str
    nodes: list[str]
    edges: list[tuple[str, str]]
    conditional_edges: list[ConditionalEdge] = field(default_factory=list)
    entry: str = "planner"  # first node after START


def _resolve(name: str) -> str:
    """Map symbolic names to LangGraph constants."""
    if name == "START":
        return START
    if name == "END":
        return END
    return name


def compile_graph(
    spec: GraphSpec,
    node_registry: dict[str, Callable],
    condition_registry: dict[str, Callable],
    checkpointer: Any | None = None,
) -> Any:
    """Compile a GraphSpec into a compiled LangGraph StateGraph."""
    g = StateGraph(FlowGraphState)

    for node_name in spec.nodes:
        fn = node_registry.get(node_name)
        if fn is None:
            raise ValueError(f"No node function registered for '{node_name}'")
        g.add_node(node_name, fn)

    g.add_edge(START, spec.entry)

    for src, dst in spec.edges:
        g.add_edge(_resolve(src), _resolve(dst))

    for ce in spec.conditional_edges:
        condition_fn = condition_registry.get(ce.condition)
        if condition_fn is None:
            raise ValueError(f"No condition function registered for '{ce.condition}'")
        resolved_mapping = {k: _resolve(v) for k, v in ce.mapping.items()}
        g.add_conditional_edges(ce.source, condition_fn, resolved_mapping)

    return g.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Built-in template specs
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, GraphSpec] = {
    "linear-3": GraphSpec(
        template="linear-3",
        nodes=["planner", "worker", "synthesizer"],
        edges=[
            ("planner", "worker"),
            ("worker", "synthesizer"),
            ("synthesizer", "END"),
        ],
        entry="planner",
    ),

    "deer_flow": GraphSpec(  # alias kept for existing agents
        template="deer_flow",
        nodes=["planner", "worker", "synthesizer"],
        edges=[
            ("planner", "worker"),
            ("worker", "synthesizer"),
            ("synthesizer", "END"),
        ],
        entry="planner",
    ),

    "researcher-critic-writer": GraphSpec(
        template="researcher-critic-writer",
        nodes=["researcher", "critic", "writer"],
        edges=[
            ("writer", "END"),
        ],
        conditional_edges=[
            ConditionalEdge(
                source="critic",
                condition="should_continue_research",
                mapping={
                    "researcher": "researcher",
                    "writer": "writer",
                },
            )
        ],
        entry="researcher",
    ),

    "human-in-loop": GraphSpec(
        template="human-in-loop",
        nodes=["planner", "human_gate", "worker", "synthesizer"],
        edges=[
            ("planner", "human_gate"),
            ("worker", "synthesizer"),
            ("synthesizer", "END"),
        ],
        conditional_edges=[
            ConditionalEdge(
                source="human_gate",
                condition="gate_approved",
                mapping={
                    "approved": "worker",
                    "waiting": "human_gate",
                },
            )
        ],
        entry="planner",
    ),
}


def spec_from_config(agent_config: dict[str, Any]) -> GraphSpec:
    """Resolve a GraphSpec from agent_config, falling back to linear-3."""
    graph_cfg = agent_config.get("graph")
    if isinstance(graph_cfg, dict):
        template = graph_cfg.get("template", "linear-3")
    elif isinstance(agent_config.get("template"), str):
        # Legacy: top-level template field
        template = agent_config["template"]
    else:
        template = "linear-3"

    spec = TEMPLATES.get(template)
    if spec is None:
        spec = TEMPLATES["linear-3"]
    return spec
