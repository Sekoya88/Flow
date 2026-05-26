"""LangChain MCP adapter — loads tools from registered MCP servers for a workspace."""

from __future__ import annotations

import asyncio
from uuid import UUID

from flow.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)

_CONNECT_TIMEOUT = 10.0


def _sse_url(url: str, jwt_token: str = "") -> str:
    sse = url if url.endswith("/sse") else f"{url.rstrip('/')}/sse"
    return f"{sse}?token={jwt_token}" if jwt_token else sse


async def get_mcp_tools_for_agent(
    workspace_id: UUID,
    jwt_token: str,
    pool,
) -> list:
    """Return LangChain tools from all active MCP servers for the workspace."""
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        logger.warning("mcp_client.langchain_mcp_adapters_not_installed")
        return []

    rows = await pool.fetch(
        "SELECT * FROM mcp_servers WHERE workspace_id = $1 AND active = true",
        workspace_id,
    )
    if not rows:
        return []

    server_configs: dict[str, dict] = {
        str(row["id"]): {"transport": "sse", "url": _sse_url(row["url"], jwt_token)}
        for row in rows
    }

    try:
        client = MultiServerMCPClient(server_configs)
        tools = await client.get_tools()
        logger.info("mcp_client.tools_loaded", count=len(tools), workspace_id=str(workspace_id))
        return tools
    except Exception:
        logger.exception("mcp_client.failed_to_load_tools", workspace_id=str(workspace_id))
        return []


async def list_tools_for_server(url: str, jwt_token: str = "") -> list[dict]:
    """Connect to a single MCP server and return its tool list with descriptions."""
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        logger.warning("mcp_client.langchain_mcp_adapters_not_installed")
        return []

    config = {"_server": {"transport": "sse", "url": _sse_url(url, jwt_token)}}
    try:
        async with asyncio.timeout(_CONNECT_TIMEOUT):
            client = MultiServerMCPClient(config)
            tools = await client.get_tools()
            return [{"tool_name": t.name, "description": t.description or ""} for t in tools]
    except TimeoutError:
        logger.warning("mcp_client.list_tools_timeout", url=url)
        return []
    except Exception:
        logger.exception("mcp_client.list_tools_failed", url=url)
        return []


async def invoke_tool_on_server(
    url: str, tool_name: str, args: dict, jwt_token: str = ""
) -> dict:
    """Invoke a named tool on an MCP server via the real MCP protocol."""
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        return {"ok": False, "error": "langchain_mcp_adapters not installed"}

    config = {"_server": {"transport": "sse", "url": _sse_url(url, jwt_token)}}
    try:
        async with asyncio.timeout(_CONNECT_TIMEOUT):
            client = MultiServerMCPClient(config)
            tools = await client.get_tools()
            tool = next((t for t in tools if t.name == tool_name), None)
            if tool is None:
                return {"ok": False, "error": f"tool '{tool_name}' not found on server"}
            result = await tool.ainvoke(args)
            return {"ok": True, "result": result}
    except TimeoutError:
        return {"ok": False, "error": "MCP server connection timed out"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
