from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_bearer_token, get_current_user_id, get_repo

router = APIRouter(prefix="/api/v1/mcp", tags=["MCP"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class MCPServerCreateIn(BaseModel):
    workspace_id: UUID
    name: str
    url: str
    transport: str = "sse"
    metadata: dict = {}


class MCPServerPatchIn(BaseModel):
    name: str | None = None
    url: str | None = None
    active: bool | None = None
    metadata: dict | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _assert_workspace(user_id: UUID, workspace_id: UUID, repo: FlowRepository) -> None:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    if workspace_id not in {r["id"] for r in ws_rows}:
        raise HTTPException(status_code=403, detail="workspace not allowed")


async def _get_server_or_404(server_id: UUID, repo: FlowRepository) -> dict:
    row = await repo._pool.fetchrow("SELECT * FROM mcp_servers WHERE id = $1", server_id)
    if not row:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return dict(row)


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/servers")
async def list_mcp_servers(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> list:
    await _assert_workspace(user_id, workspace_id, repo)
    rows = await repo._pool.fetch(
        """
        SELECT s.*,
               COUNT(a.id)::int AS tool_count
        FROM mcp_servers s
        LEFT JOIN mcp_server_tool_assignments a ON a.mcp_server_id = s.id
        WHERE s.workspace_id = $1
        GROUP BY s.id
        ORDER BY s.created_at DESC
        """,
        workspace_id,
    )
    return [dict(r) for r in rows]


@router.post("/servers", status_code=201)
async def create_mcp_server(
    body: MCPServerCreateIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await _assert_workspace(user_id, body.workspace_id, repo)
    row = await repo._pool.fetchrow(
        """
        INSERT INTO mcp_servers (workspace_id, name, url, transport, metadata)
        VALUES ($1, $2, $3, $4, $5::jsonb)
        RETURNING *
        """,
        body.workspace_id,
        body.name,
        body.url,
        body.transport,
        json.dumps(body.metadata),
    )
    return dict(row)


@router.patch("/servers/{server_id}")
async def patch_mcp_server(
    server_id: UUID,
    body: MCPServerPatchIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    row = await _get_server_or_404(server_id, repo)
    await _assert_workspace(user_id, row["workspace_id"], repo)

    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if "metadata" in updates:
        updates["metadata"] = json.dumps(updates["metadata"])
    if not updates:
        return row

    _JSONB_COLS = {"metadata"}
    set_clauses = ", ".join(f"{col} = ${i + 2}::jsonb" if col in _JSONB_COLS else f"{col} = ${i + 2}" for i, col in enumerate(updates))
    values = [server_id, *updates.values()]
    updated = await repo._pool.fetchrow(
        f"UPDATE mcp_servers SET {set_clauses}, updated_at = now() WHERE id = $1 RETURNING *",
        *values,
    )
    return dict(updated)


@router.delete("/servers/{server_id}", status_code=204)
async def delete_mcp_server(
    server_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> None:
    row = await repo._pool.fetchrow("SELECT workspace_id FROM mcp_servers WHERE id = $1", server_id)
    if not row:
        raise HTTPException(status_code=404, detail="MCP server not found")
    await _assert_workspace(user_id, row["workspace_id"], repo)
    await repo._pool.execute("DELETE FROM mcp_servers WHERE id = $1", server_id)


@router.get("/servers/{server_id}/ping")
async def ping_mcp_server(
    server_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    row = await _get_server_or_404(server_id, repo)
    await _assert_workspace(user_id, row["workspace_id"], repo)

    import httpx

    health_url = row["url"].rstrip("/").rsplit("/sse", 1)[0] + "/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(health_url)
            return {"ok": r.status_code < 400, "status_code": r.status_code}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/servers/{server_id}/tools")
async def list_mcp_server_tools(
    server_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> list:
    """Return cached tool list from the last sync."""
    row = await _get_server_or_404(server_id, repo)
    await _assert_workspace(user_id, row["workspace_id"], repo)

    rows = await repo._pool.fetch(
        "SELECT * FROM mcp_server_tool_assignments WHERE mcp_server_id = $1 ORDER BY tool_name",
        server_id,
    )
    return [dict(r) for r in rows]


@router.post("/servers/{server_id}/tools/sync")
async def sync_mcp_server_tools(
    server_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    token: Annotated[str, Depends(get_bearer_token)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Connect to the MCP server live, discover tools, upsert into cache, return results."""
    row = await _get_server_or_404(server_id, repo)
    await _assert_workspace(user_id, row["workspace_id"], repo)

    from flow.infrastructure.llm.mcp_client import list_tools_for_server

    tools = await list_tools_for_server(row["url"], jwt_token=token)

    async with repo._pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM mcp_server_tool_assignments WHERE mcp_server_id = $1 AND agent_id IS NULL",
            server_id,
        )
        for t in tools:
            await conn.execute(
                """
                INSERT INTO mcp_server_tool_assignments (mcp_server_id, tool_name, description, enabled)
                VALUES ($1, $2, $3, true)
                """,
                server_id,
                t["tool_name"],
                t.get("description") or "",
            )

    return {"ok": True, "tool_count": len(tools), "tools": tools}


@router.post("/servers/{server_id}/tools/{tool_name}/invoke")
async def invoke_mcp_tool(
    server_id: UUID,
    tool_name: str,
    body: dict[str, Any],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    token: Annotated[str, Depends(get_bearer_token)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Playground: invoke a tool on an MCP server via the real MCP protocol."""
    row = await _get_server_or_404(server_id, repo)
    await _assert_workspace(user_id, row["workspace_id"], repo)

    from flow.infrastructure.llm.mcp_client import invoke_tool_on_server

    return await invoke_tool_on_server(row["url"], tool_name, body, jwt_token=token)
