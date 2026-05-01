"""Wire LangSmith / LangChain tracing from Flow settings.

LangChain and LangGraph read LANGCHAIN_* env vars at runtime.
See: https://docs.smith.langchain.com/

FLOW_LANGSMITH_* maps to LANGCHAIN_* so compose can keep the FLOW_ prefix.
Also accepts plain LANGSMITH_* / LANGCHAIN_* when the host only exports those names.
"""

from __future__ import annotations

import os

from flow.config import Settings


def _strip_env_quotes(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
        return v[1:-1].strip()
    return v


def configure_langsmith(settings: Settings) -> None:
    """Set LANGCHAIN_* env vars for LangChain / LangGraph.

    Must run before importing langgraph/langchain in the process (see worker entry).

    Resolution order: Settings (FLOW_*), then LANGSMITH_*, then LANGCHAIN_*.
    """
    from flow.infrastructure.observability.logging import get_logger

    log = get_logger("flow.langsmith")
    key = (
        _strip_env_quotes((settings.langsmith_api_key or "").strip())
        or _strip_env_quotes((os.getenv("LANGSMITH_API_KEY") or "").strip())
        or _strip_env_quotes((os.getenv("LANGCHAIN_API_KEY") or "").strip())
    )
    if not key:
        log.debug("langsmith.disabled", reason="no_api_key")
        return

    tracing = settings.langsmith_tracing
    lt = (os.getenv("LANGSMITH_TRACING") or "").strip().lower()
    if lt in ("0", "false", "no"):
        tracing = False
    elif lt in ("1", "true", "yes"):
        tracing = True
    if not tracing:
        log.debug("langsmith.disabled", reason="tracing_disabled")
        return

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = key

    project_raw = (
        _strip_env_quotes((settings.langsmith_project or "").strip())
        or _strip_env_quotes(os.getenv("LANGSMITH_PROJECT") or "")
        or _strip_env_quotes(os.getenv("LANGCHAIN_PROJECT") or "")
        or "flow"
    )
    project = project_raw.strip() or "flow"
    os.environ["LANGCHAIN_PROJECT"] = project

    endpoint_raw = (
        (settings.langsmith_endpoint or "").strip()
        or (os.getenv("LANGSMITH_ENDPOINT") or "").strip()
        or (os.getenv("LANGCHAIN_ENDPOINT") or "").strip()
    )
    endpoint = _strip_env_quotes(endpoint_raw).strip()
    if endpoint:
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint.rstrip("/")
    log.info("langsmith.enabled", project=project, endpoint=endpoint or "default")
