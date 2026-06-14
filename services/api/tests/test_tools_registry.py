"""Registry ↔ executor parity gate.

The tool registry (`all_specs()`) is what the UI tool picker advertises via
GET /api/v1/tools. Every advertised tool MUST be backed by the execution layer,
otherwise a user can enable a tool that silently does nothing — or worse, a
tool that was never meant to be reachable by an LLM (arbitrary file read, SSRF,
raw SQL). This test pins the registry to the set the executor actually honours.

Sources of truth for the canonical set:
- `routes/agents.py` tool_keys: retrieve, sandbox, long_term_memory,
  tavily_search, fetch_webpage, arxiv_search, hf_papers
- `graph/nodes.py`: subagent_call (always built), long_term_memory recall,
  and the _build_context_tools StructuredTool branches
"""

from __future__ import annotations

from flow.infrastructure.tools.registry import all_specs

# Tools the execution layer genuinely supports. Keep in sync with the executor.
_EXECUTOR_SUPPORTED = {
    "retrieve",
    "sandbox",
    "long_term_memory",
    "subagent_call",
    "tavily_search",
    "fetch_webpage",
    "arxiv_search",
    "hf_papers",
}

# Tools removed from the registry: unwired, no implementation, or an LLM-driven
# security liability (arbitrary file read / SSRF / raw SQL). They must not be
# re-advertised without first wiring a guarded executor path.
_BANNED = {"http_get", "http_post", "sql_query", "file_read", "pdf_extract", "csv_query", "date_lookup"}


def _registry_names() -> set[str]:
    return {spec.name for spec in all_specs()}


def test_every_advertised_tool_is_executor_supported() -> None:
    """No registry entry may advertise a capability the executor cannot honour."""
    unsupported = _registry_names() - _EXECUTOR_SUPPORTED
    assert not unsupported, f"registry advertises unwired tools: {unsupported}"


def test_all_supported_tools_are_advertised() -> None:
    """Every executor-supported tool must appear in the catalog the UI reads."""
    missing = _EXECUTOR_SUPPORTED - _registry_names()
    assert not missing, f"executor supports tools not advertised: {missing}"


def test_banned_tools_are_not_advertised() -> None:
    """Regression: dangerous/phantom tools stay out of the catalog."""
    leaked = _BANNED & _registry_names()
    assert not leaked, f"dangerous/phantom tools re-advertised: {leaked}"


def test_knowledge_tool_uses_executor_key() -> None:
    """The knowledge tool must be advertised under the key the executor reads."""
    names = _registry_names()
    assert "retrieve" in names
    assert "knowledge_search" not in names  # old name read a key the executor ignored


# ── tool_scope least-privilege ──────────────────────────────────────────────


def test_no_scope_anywhere_is_unrestricted() -> None:
    from flow.infrastructure.tools.registry import resolve_tool_scope

    assert resolve_tool_scope({}, None) is None
    assert resolve_tool_scope({"tool_scope": "*"}, None) is None


def test_own_scope_limits_tools() -> None:
    from flow.infrastructure.tools.registry import resolve_tool_scope

    assert resolve_tool_scope({"tool_scope": ["retrieve", "sandbox"]}, None) == {"retrieve", "sandbox"}


def test_child_cannot_widen_parent_scope() -> None:
    from flow.infrastructure.tools.registry import resolve_tool_scope

    parent = ["retrieve", "tavily_search"]
    # Child asks for more than the parent allows → intersection only.
    child_cfg = {"tool_scope": ["retrieve", "sandbox", "subagent_call"]}
    assert resolve_tool_scope(child_cfg, parent) == {"retrieve"}


def test_child_inherits_parent_ceiling_when_child_unrestricted() -> None:
    from flow.infrastructure.tools.registry import resolve_tool_scope

    assert resolve_tool_scope({}, ["retrieve"]) == {"retrieve"}


def test_is_tool_allowed() -> None:
    from flow.infrastructure.tools.registry import is_tool_allowed

    assert is_tool_allowed("retrieve", None) is True  # unrestricted
    assert is_tool_allowed("retrieve", {"retrieve"}) is True
    assert is_tool_allowed("sandbox", {"retrieve"}) is False
