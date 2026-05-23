"""LangChain MCP adapter — loads tools from registered MCP servers for a workspace."""

from __future__ import annotations

from uuid import UUID

from flow.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


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

    server_configs: dict[str, dict] = {}
    for row in rows:
        url = row["url"]
        sse_url = url if url.endswith("/sse") else f"{url.rstrip('/')}/sse"
        server_configs[str(row["id"])] = {
            "transport": "sse",
            "url": f"{sse_url}?token={jwt_token}",
        }

    try:
        async with MultiServerMCPClient(server_configs) as client:
            tools = client.get_tools()
            logger.info("mcp_client.tools_loaded", count=len(tools), workspace_id=str(workspace_id))
            return tools
    except Exception:
        logger.exception("mcp_client.failed_to_load_tools", workspace_id=str(workspace_id))
        return []
