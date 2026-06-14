"""Tool plugin registry.

Tools register themselves as ToolSpec instances. The registry is populated at
import time from built-in tools and from Python entry-points
(group="flow.tools") so external packages auto-register on install.
"""

from __future__ import annotations

import importlib.metadata
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    required_capabilities: list[str] = field(default_factory=list)
    # Optional async run callable; may be None for metadata-only entries
    run: Callable[..., Coroutine[Any, Any, Any]] | None = None


_REGISTRY: dict[str, ToolSpec] = {}


def register(spec: ToolSpec) -> None:
    _REGISTRY[spec.name] = spec


def get(name: str) -> ToolSpec | None:
    return _REGISTRY.get(name)


def all_specs() -> list[ToolSpec]:
    return list(_REGISTRY.values())


def names_for_agent(agent_config: dict[str, Any]) -> list[str]:
    """Return list of tool names enabled for this agent config."""
    tools_cfg = agent_config.get("tools")
    if not isinstance(tools_cfg, dict):
        return list(_REGISTRY.keys())
    enabled = []
    for name in _REGISTRY:
        if tools_cfg.get(name, True):
            enabled.append(name)
    return enabled


def resolve_tool_scope(
    agent_config: dict[str, Any],
    parent_scope: list[str] | None = None,
) -> set[str] | None:
    """Compute the least-privilege ceiling of tool names this agent may use.

    - ``tool_scope`` in the config is an allowlist; ``"*"`` (or missing) = no
      ceiling of its own.
    - ``parent_scope`` is the ceiling inherited from a calling agent. A subagent
      can never widen its parent's scope, so the two are intersected.

    Returns a set of allowed names, or ``None`` meaning "unrestricted" (no
    allowlist anywhere in the chain). Callers still apply the per-tool on/off
    toggles separately — this only caps what *can* be enabled.
    """
    own = agent_config.get("tool_scope")
    own_set: set[str] | None
    if own in (None, "*") or not isinstance(own, list):
        own_set = None
    else:
        own_set = {str(n) for n in own}

    parent_set = set(parent_scope) if parent_scope is not None else None

    if own_set is None:
        return parent_set
    if parent_set is None:
        return own_set
    return own_set & parent_set


def is_tool_allowed(name: str, scope: set[str] | None) -> bool:
    """True if *name* is permitted under *scope* (None = unrestricted)."""
    return scope is None or name in scope


# ---------------------------------------------------------------------------
# Built-in tool registrations
# ---------------------------------------------------------------------------

register(
    ToolSpec(
        name="retrieve",
        description="Semantic search over workspace knowledge sources. Returns relevant text chunks.",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "default": 4},
            },
            "required": ["query"],
        },
        required_capabilities=["retrieve"],
    )
)

register(
    ToolSpec(
        name="sandbox",
        description="Execute Python code in an isolated sandbox (e2b or Docker). Returns stdout/stderr.",
        parameters_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
                "timeout": {"type": "integer", "default": 30, "description": "Timeout in seconds"},
            },
            "required": ["code"],
        },
        required_capabilities=["sandbox"],
    )
)

register(
    ToolSpec(
        name="long_term_memory",
        description="Recall agent memories for the current user + workspace. Returns relevant past memories.",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Memory recall query"},
                "limit": {"type": "integer", "default": 4},
            },
            "required": ["query"],
        },
        required_capabilities=["long_term_memory"],
    )
)

register(
    ToolSpec(
        name="subagent_call",
        description="Invoke another agent in the workspace as a subagent. Returns the subagent's answer.",
        parameters_schema={
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "Name of the target agent"},
                "message": {"type": "string", "description": "Message to send to the subagent"},
            },
            "required": ["agent_name", "message"],
        },
        required_capabilities=[],
    )
)

register(
    ToolSpec(
        name="tavily_search",
        description="Search the web with Tavily. Use for current events, factual queries, or any web search. Requires FLOW_TAVILY_API_KEY.",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        required_capabilities=["tavily_search"],
    )
)

register(
    ToolSpec(
        name="fetch_webpage",
        description="Fetch and extract readable text from any URL. Good for reading articles, documentation, or paper abstracts.",
        parameters_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
            },
            "required": ["url"],
        },
        required_capabilities=[],
    )
)

register(
    ToolSpec(
        name="arxiv_search",
        description="Search ArXiv for academic papers by query. Returns title, abstract, URL, and publish date.",
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        required_capabilities=[],
    )
)

register(
    ToolSpec(
        name="hf_papers",
        description="Fetch HuggingFace Daily Papers. Returns top AI/ML papers of the day with title, abstract, and upvotes.",
        parameters_schema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format. Leave empty for today."},
            },
            "required": [],
        },
        required_capabilities=[],
    )
)

# ---------------------------------------------------------------------------
# Load external tools from entry-points (silently skip failures)
# ---------------------------------------------------------------------------


def _load_entry_point_tools() -> None:
    try:
        eps = importlib.metadata.entry_points(group="flow.tools")
    except Exception:
        return
    for ep in eps:
        try:
            spec_obj = ep.load()
            if isinstance(spec_obj, ToolSpec):
                register(spec_obj)
                logger.info("tool.registered_via_entrypoint name=%s", spec_obj.name)
        except Exception as exc:
            logger.warning("tool.entrypoint_load_failed name=%s error=%s", ep.name, exc)


_load_entry_point_tools()
