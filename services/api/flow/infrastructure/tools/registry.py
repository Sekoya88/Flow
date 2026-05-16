"""Tool plugin registry.

Tools register themselves as ToolSpec instances. The registry is populated at
import time from built-in tools and from Python entry-points
(group="flow.tools") so external packages auto-register on install.
"""
from __future__ import annotations

import importlib.metadata
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

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


# ---------------------------------------------------------------------------
# Built-in tool registrations
# ---------------------------------------------------------------------------

register(ToolSpec(
    name="knowledge_search",
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
))

register(ToolSpec(
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
))

register(ToolSpec(
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
))

register(ToolSpec(
    name="http_get",
    description="Perform an HTTP GET request and return the response body (truncated to 8KB).",
    parameters_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "headers": {"type": "object", "description": "Optional request headers"},
        },
        "required": ["url"],
    },
    required_capabilities=[],
))

register(ToolSpec(
    name="sql_query",
    description="Run a read-only SQL query against the workspace database (SELECT only).",
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "SQL SELECT query"},
        },
        "required": ["query"],
    },
    required_capabilities=[],
))

register(ToolSpec(
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
))

register(ToolSpec(
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
))

register(ToolSpec(
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
))

register(ToolSpec(
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
))

register(ToolSpec(
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
))

register(ToolSpec(
    name="file_read",
    description="Read a local file by path and return its text content (up to 32KB).",
    parameters_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute or relative file path"},
            "encoding": {"type": "string", "default": "utf-8", "description": "File encoding"},
        },
        "required": ["path"],
    },
    required_capabilities=[],
))

register(ToolSpec(
    name="pdf_extract",
    description="Extract structured text, section headings, and page count from a PDF file.",
    parameters_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the PDF file"},
        },
        "required": ["path"],
    },
    required_capabilities=[],
))

register(ToolSpec(
    name="http_post",
    description="Perform an HTTP POST/PUT/PATCH/DELETE request and return status code and response body.",
    parameters_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Request URL"},
            "json_body": {"type": "object", "description": "JSON request body"},
            "headers": {"type": "object", "description": "Optional request headers"},
            "method": {"type": "string", "default": "POST", "description": "HTTP method: POST, PUT, PATCH, DELETE"},
        },
        "required": ["url"],
    },
    required_capabilities=[],
))

register(ToolSpec(
    name="csv_query",
    description="Query a CSV string: select columns, filter rows by condition, and limit output.",
    parameters_schema={
        "type": "object",
        "properties": {
            "csv_text": {"type": "string", "description": "Raw CSV content with header row"},
            "select": {"type": "array", "items": {"type": "string"}, "description": "Columns to include (default: all)"},
            "filter_col": {"type": "string", "description": "Column to filter on"},
            "filter_op": {"type": "string", "description": "Operator: eq, ne, gt, lt, gte, lte, contains"},
            "filter_val": {"type": "string", "description": "Value to compare against"},
            "limit": {"type": "integer", "default": 100, "description": "Max rows returned"},
        },
        "required": ["csv_text"],
    },
    required_capabilities=[],
))

register(ToolSpec(
    name="date_lookup",
    description="Parse, convert, and format date/time expressions. Supports timezone conversion and relative terms like 'now'.",
    parameters_schema={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "default": "now", "description": "Date string or 'now'/'today'"},
            "from_tz": {"type": "string", "default": "UTC", "description": "Source IANA timezone"},
            "to_tz": {"type": "string", "default": "UTC", "description": "Target IANA timezone"},
            "output_format": {"type": "string", "default": "%Y-%m-%d %H:%M:%S %Z", "description": "strftime format"},
        },
        "required": [],
    },
    required_capabilities=[],
))


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
