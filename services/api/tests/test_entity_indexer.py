import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from flow.infrastructure.graph.entity_indexer import (
    index_agent,
    index_execution,
    index_genome,
    index_skill,
)


def _make_pool(fetch_row_return=None, fetch_return=None):
    """Create a mock asyncpg pool that records calls."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetch_row_return)
    conn.fetch = AsyncMock(return_value=fetch_return or [])
    conn.execute = AsyncMock(return_value="INSERT 1")
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)
    return pool, conn


@pytest.mark.asyncio
async def test_index_agent_upserts_node():
    pool, conn = _make_pool()
    agent_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    await index_agent(
        pool,
        workspace_id=workspace_id,
        agent_id=agent_id,
        name="ResearchBot",
        template="react-agent",
    )

    conn.fetchrow.assert_called_once()
    call_sql = conn.fetchrow.call_args[0][0]
    assert "INSERT INTO kg_nodes" in call_sql
    assert "ON CONFLICT" in call_sql
    call_args = conn.fetchrow.call_args[0]
    assert "agent" in call_args  # node_type
    assert str(agent_id) in call_args  # ref_id


@pytest.mark.asyncio
async def test_index_skill_creates_has_skill_edge():
    agent_node_id = uuid.uuid4()
    pool, conn = _make_pool(fetch_row_return={"id": agent_node_id})
    skill_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    # fetchrow called twice: agent lookup + skill upsert
    conn.fetchrow = AsyncMock(
        side_effect=[
            {"id": agent_node_id},  # agent lookup
            {"id": uuid.uuid4()},  # skill upsert RETURNING id
        ]
    )

    await index_skill(
        pool,
        workspace_id=workspace_id,
        agent_id=agent_id,
        skill_id=skill_id,
        name="web-search",
        version=1,
        score=0.85,
    )

    # edge insert should have been called
    assert conn.execute.called
    edge_sql = conn.execute.call_args[0][0]
    assert "kg_edges" in edge_sql
    assert "has_skill" in conn.execute.call_args[0]


@pytest.mark.asyncio
async def test_index_genome_creates_prev_version_edge():
    prev_id = uuid.uuid4()
    genome_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    conn = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    # Calls: agent lookup, genome upsert, prompt upsert, prev genome lookup
    conn.fetchrow = AsyncMock(
        side_effect=[
            {"id": uuid.uuid4()},  # agent node
            {"id": uuid.uuid4()},  # genome upsert RETURNING
            {"id": uuid.uuid4()},  # prompt upsert RETURNING
            {"id": uuid.uuid4()},  # prev genome node
        ]
    )
    conn.execute = AsyncMock()
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)

    await index_genome(
        pool,
        workspace_id=workspace_id,
        agent_id=agent_id,
        genome_id=genome_id,
        version_label="3",
        provider="openai",
        model="gpt-4o",
        status="active",
        system_prompt="You are a research assistant.",
        prev_genome_id=prev_id,
    )

    edge_calls = [str(c) for c in conn.execute.call_args_list]
    assert any("prev_version" in c for c in edge_calls)


@pytest.mark.asyncio
async def test_index_execution_idempotent_on_missing_agent():
    """If agent node not yet indexed, execution still inserts without crashing."""
    pool, conn = _make_pool(fetch_row_return=None)
    conn.fetchrow = AsyncMock(
        side_effect=[
            None,  # agent not found — no has_ran edge
            {"id": uuid.uuid4()},  # execution upsert RETURNING
        ]
    )

    await index_execution(
        pool,
        workspace_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        execution_id=uuid.uuid4(),
        status="completed",
        skill_ids=[],
    )

    # execution node upserted, no crash
    assert conn.fetchrow.called
