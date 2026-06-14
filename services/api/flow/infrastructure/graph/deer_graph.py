"""deer_graph — thin entry point that compiles a GraphSpec for a given agent config.

The actual node logic lives in nodes.py; template topology in spec.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg

from flow.config import Settings
from flow.infrastructure.graph.nodes import CONDITION_REGISTRY, build_node_registry
from flow.infrastructure.graph.spec import compile_graph, spec_from_config


@dataclass
class GraphContext:
    pool: asyncpg.Pool
    workspace_id: UUID
    agent_id: UUID
    user_id: UUID
    openai_api_key: str | None
    agent_config: dict[str, Any]
    anthropic_api_key: str | None = None
    execution_id: UUID | None = None
    settings: Settings | None = None
    stream_hub: Any | None = None  # ExecutionStreamHub — avoids circular import
    store: Any | None = None  # AsyncPostgresStore for cross-thread memory
    # Stream namespace for child runs (e.g. "subagent:researcher"). When set, events
    # emitted by this context are tagged with `ns` so the parent run UI can scope them
    # — mirrors deepagents' stream.subagents namespacing.
    stream_namespace: str | None = None
    # Least-privilege tool ceiling inherited from a parent agent. None = unrestricted.
    # A subagent's effective tools are its own enabled set ∩ this ceiling, so a child
    # can never call a tool the parent could not.
    parent_tool_scope: list[str] | None = None


def build_deer_flow_graph(ctx: GraphContext, checkpointer: Any | None = None) -> Any:
    spec = spec_from_config(ctx.agent_config)
    node_registry = build_node_registry(ctx)
    return compile_graph(spec, node_registry, CONDITION_REGISTRY, checkpointer=checkpointer, store=ctx.store)
