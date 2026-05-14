"""Syncs Flow entities into kg_nodes/kg_edges on every write.

All functions are idempotent — safe to call on create and update.
Uses ON CONFLICT on (workspace_id, ref_type, ref_id) unique index.
"""
from __future__ import annotations

import uuid
from typing import Any

import asyncpg


async def _upsert_node(
    conn: asyncpg.Connection,
    *,
    workspace_id: uuid.UUID,
    node_type: str,
    ref_id: str,
    label: str,
    metadata: dict[str, Any],
) -> uuid.UUID | None:
    row = await conn.fetchrow(
        """
        INSERT INTO kg_nodes
            (id, workspace_id, node_type, ref_id, ref_type, label, metadata)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (workspace_id, ref_type, ref_id) WHERE ref_id IS NOT NULL
        DO UPDATE SET
            label      = EXCLUDED.label,
            metadata   = EXCLUDED.metadata,
            updated_at = now()
        RETURNING id
        """,
        uuid.uuid4(), workspace_id, node_type, ref_id, node_type, label, metadata,
    )
    return row["id"] if row is not None else None


async def _upsert_edge(
    conn: asyncpg.Connection,
    *,
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    edge_type: str,
) -> None:
    await conn.execute(
        """
        INSERT INTO kg_edges (id, workspace_id, source_id, target_id, edge_type)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (source_id, target_id, edge_type) DO NOTHING
        """,
        uuid.uuid4(), workspace_id, source_id, target_id, edge_type,
    )


async def index_agent(
    pool: asyncpg.Pool,
    *,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    name: str,
    template: str,
    status: str = "active",
) -> None:
    async with pool.acquire() as conn:
        await _upsert_node(
            conn,
            workspace_id=workspace_id,
            node_type="agent",
            ref_id=str(agent_id),
            label=name,
            metadata={"template": template, "status": status},
        )


async def index_skill(
    pool: asyncpg.Pool,
    *,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    skill_id: uuid.UUID,
    name: str,
    version: int,
    score: float,
) -> None:
    async with pool.acquire() as conn:
        agent_node = await conn.fetchrow(
            "SELECT id FROM kg_nodes WHERE workspace_id=$1 AND ref_type='agent' AND ref_id=$2",
            workspace_id, str(agent_id),
        )
        skill_node_id = await _upsert_node(
            conn,
            workspace_id=workspace_id,
            node_type="skill",
            ref_id=str(skill_id),
            label=name,
            metadata={"version": version, "score": score},
        )
        if agent_node and skill_node_id is not None:
            await _upsert_edge(
                conn,
                workspace_id=workspace_id,
                source_id=agent_node["id"],
                target_id=skill_node_id,
                edge_type="has_skill",
            )


async def index_genome(
    pool: asyncpg.Pool,
    *,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    genome_id: uuid.UUID,
    version_label: str,
    provider: str,
    model: str,
    status: str,
    system_prompt: str | None,
    prev_genome_id: uuid.UUID | None,
) -> None:
    async with pool.acquire() as conn:
        agent_node = await conn.fetchrow(
            "SELECT id FROM kg_nodes WHERE workspace_id=$1 AND ref_type='agent' AND ref_id=$2",
            workspace_id, str(agent_id),
        )
        genome_node_id = await _upsert_node(
            conn,
            workspace_id=workspace_id,
            node_type="genome_version",
            ref_id=str(genome_id),
            label=f"v{version_label}",
            metadata={"provider": provider, "model": model, "status": status},
        )
        if agent_node and genome_node_id is not None:
            await _upsert_edge(
                conn,
                workspace_id=workspace_id,
                source_id=agent_node["id"],
                target_id=genome_node_id,
                edge_type="has_genome",
            )
        if system_prompt and genome_node_id is not None:
            prompt_node_id = await _upsert_node(
                conn,
                workspace_id=workspace_id,
                node_type="system_prompt",
                ref_id=f"{genome_id}:prompt",
                label="system_prompt",
                metadata={"preview": system_prompt[:200]},
            )
            if prompt_node_id is not None:
                await _upsert_edge(
                    conn,
                    workspace_id=workspace_id,
                    source_id=genome_node_id,
                    target_id=prompt_node_id,
                    edge_type="uses_prompt",
                )
        if prev_genome_id and genome_node_id is not None:
            prev_node = await conn.fetchrow(
                "SELECT id FROM kg_nodes "
                "WHERE workspace_id=$1 AND ref_type='genome_version' AND ref_id=$2",
                workspace_id, str(prev_genome_id),
            )
            if prev_node:
                await _upsert_edge(
                    conn,
                    workspace_id=workspace_id,
                    source_id=genome_node_id,
                    target_id=prev_node["id"],
                    edge_type="prev_version",
                )


async def index_execution(
    pool: asyncpg.Pool,
    *,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    execution_id: uuid.UUID,
    status: str,
    skill_ids: list[uuid.UUID],
) -> None:
    async with pool.acquire() as conn:
        agent_node = await conn.fetchrow(
            "SELECT id FROM kg_nodes WHERE workspace_id=$1 AND ref_type='agent' AND ref_id=$2",
            workspace_id, str(agent_id),
        )
        exec_node_id = await _upsert_node(
            conn,
            workspace_id=workspace_id,
            node_type="execution",
            ref_id=str(execution_id),
            label=str(execution_id)[:8],
            metadata={"status": status},
        )
        if agent_node and exec_node_id is not None:
            await _upsert_edge(
                conn,
                workspace_id=workspace_id,
                source_id=agent_node["id"],
                target_id=exec_node_id,
                edge_type="ran",
            )
        for skill_id in skill_ids:
            skill_node = await conn.fetchrow(
                "SELECT id FROM kg_nodes "
                "WHERE workspace_id=$1 AND ref_type='skill' AND ref_id=$2",
                workspace_id, str(skill_id),
            )
            if skill_node and exec_node_id is not None:
                await _upsert_edge(
                    conn,
                    workspace_id=workspace_id,
                    source_id=exec_node_id,
                    target_id=skill_node["id"],
                    edge_type="used_skill",
                )
