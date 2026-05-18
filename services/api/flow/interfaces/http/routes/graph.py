"""Knowledge Graph API — entity subgraph + workspace graph + position persist."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from flow.interfaces.http.deps import get_current_user_id, get_pool
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.schemas import PositionUpdateIn

router = APIRouter(prefix="/api/graph", tags=["graph"])


def _serialize_node(r: Any) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "node_type": r["node_type"],
        "ref_id": r["ref_id"],
        "ref_type": r["ref_type"],
        "label": r["label"],
        "metadata": dict(r["metadata"]) if r["metadata"] else {},
        "pos_x": r["pos_x"],
        "pos_y": r["pos_y"],
    }


def _serialize_edge(e: Any) -> dict[str, Any]:
    return {
        "id": str(e["id"]),
        "source_id": str(e["source_id"]),
        "target_id": str(e["target_id"]),
        "edge_type": e["edge_type"],
        "weight": e["weight"],
    }


async def _check_workspace_access(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    pool: asyncpg.Pool,
) -> None:
    repo = FlowRepository(pool)
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if workspace_id not in allowed:
        raise HTTPException(status_code=403, detail="workspace not allowed")


async def _fetch_workspace_graph(
    pool: asyncpg.Pool,
    workspace_id: uuid.UUID,
    type_list: list[str] | None,
    since_dt: datetime,
) -> dict[str, Any]:
    async with pool.acquire() as conn:
        base = (
            "SELECT id, node_type, ref_id, ref_type, label, metadata, pos_x, pos_y "
            "FROM kg_nodes WHERE workspace_id=$1 "
            "AND (node_type != 'execution' OR created_at >= $2)"
        )
        if type_list:
            placeholders = ", ".join(f"${i+3}" for i in range(len(type_list)))
            nodes = await conn.fetch(
                f"{base} AND node_type IN ({placeholders}) LIMIT 2000",
                workspace_id, since_dt, *type_list,
            )
        else:
            nodes = await conn.fetch(f"{base} LIMIT 2000", workspace_id, since_dt)

        node_ids = [r["id"] for r in nodes]
        if not node_ids:
            return {"nodes": [], "edges": []}

        edges = await conn.fetch(
            "SELECT id, source_id, target_id, edge_type, weight "
            "FROM kg_edges WHERE source_id = ANY($1) AND target_id = ANY($1)",
            node_ids,
        )
    return {
        "nodes": [_serialize_node(n) for n in nodes],
        "edges": [_serialize_edge(e) for e in edges],
    }


async def _fetch_entity_graph(
    pool: asyncpg.Pool,
    workspace_id: uuid.UUID,
    node_type: str,
    ref_id: str,
) -> dict[str, Any]:
    async with pool.acquire() as conn:
        root = await conn.fetchrow(
            "SELECT id, node_type, ref_id, ref_type, label, metadata, pos_x, pos_y "
            "FROM kg_nodes WHERE workspace_id=$1 AND ref_type=$2 AND ref_id=$3",
            workspace_id, node_type, ref_id,
        )
        if not root:
            raise HTTPException(status_code=404, detail="node not found")

        edges = await conn.fetch(
            "SELECT id, source_id, target_id, edge_type, weight "
            "FROM kg_edges WHERE source_id=$1 OR target_id=$1",
            root["id"],
        )
        neighbour_ids = {
            e["source_id"] if e["target_id"] == root["id"] else e["target_id"]
            for e in edges
        }
        neighbours = await conn.fetch(
            "SELECT id, node_type, ref_id, ref_type, label, metadata, pos_x, pos_y "
            "FROM kg_nodes WHERE id = ANY($1)",
            list(neighbour_ids),
        ) if neighbour_ids else []

    return {
        "node": _serialize_node(root),
        "neighbours": [_serialize_node(n) for n in neighbours],
        "edges": [_serialize_edge(e) for e in edges],
    }


async def _update_node_position(
    pool: asyncpg.Pool,
    node_id: uuid.UUID,
    workspace_id: uuid.UUID,
    x: float,
    y: float,
) -> None:
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE kg_nodes SET pos_x=$1, pos_y=$2 WHERE id=$3 AND workspace_id=$4",
            x, y, node_id, workspace_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="node not found")


@router.get("/workspace/{workspace_id}")
async def get_workspace_graph(
    workspace_id: uuid.UUID,
    types: Optional[str] = Query(None),
    since: str = Query("30d"),
    user_id: uuid.UUID = Depends(get_current_user_id),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    await _check_workspace_access(workspace_id, user_id, pool)
    days = int(since.rstrip("d")) if since.endswith("d") else 30
    since_dt = datetime.now(timezone.utc) - timedelta(days=days)
    type_list = types.split(",") if types else None
    return await _fetch_workspace_graph(pool, workspace_id, type_list, since_dt)


@router.get("/entity/{node_type}/{ref_id}")
async def get_entity_graph(
    node_type: str,
    ref_id: str,
    workspace_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, Any]:
    await _check_workspace_access(workspace_id, user_id, pool)
    return await _fetch_entity_graph(pool, workspace_id, node_type, ref_id)


@router.patch("/node/{node_id}/position")
async def update_node_position(
    node_id: uuid.UUID,
    body: PositionUpdateIn,
    workspace_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, bool]:
    await _check_workspace_access(workspace_id, user_id, pool)
    await _update_node_position(pool, node_id, workspace_id, body.x, body.y)
    return {"ok": True}
