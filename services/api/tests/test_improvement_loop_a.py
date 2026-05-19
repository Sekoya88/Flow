"""Integration tests for Loop A: reflector skill creation → genome snapshot → proposal."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


def _make_pool(agent_config=None, skill_rows=None):
    """Build a minimal asyncpg pool mock for genome_service calls."""
    pool = AsyncMock()
    conn = AsyncMock()

    agent_row = MagicMock()
    agent_row.__getitem__ = lambda self, k: (agent_config or {})[k] if k in (agent_config or {}) else None
    agent_row.get = lambda k, default=None: (agent_config or {}).get(k, default)

    conn.fetchrow = AsyncMock(
        side_effect=[
            agent_row,  # SELECT config, template FROM agents
            MagicMock(id=None),  # INSERT INTO agent_versions RETURNING id (will be replaced by execute)
        ]
    )
    conn.fetch = AsyncMock(return_value=skill_rows or [])
    conn.execute = AsyncMock()

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)

    pool.acquire = MagicMock(return_value=ctx)
    return pool, conn


@pytest.mark.asyncio
async def test_snapshot_genome_produces_candidate_version():
    """should create an agent_versions row with status=candidate for SKILL_CREATED trigger"""
    from flow.application.genome_service import snapshot_genome
    from flow.domain.genome import VersionStatus, VersionTrigger

    agent_id = uuid4()
    workspace_id = uuid4()

    pool = AsyncMock()
    conn = AsyncMock()
    agent_row = {"config": {"system_prompt": "You are helpful."}, "template": "deer_flow"}
    conn.fetchrow = AsyncMock(return_value=agent_row)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()

    ctx_mgr = AsyncMock()
    ctx_mgr.__aenter__ = AsyncMock(return_value=conn)
    ctx_mgr.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=ctx_mgr)

    version_id = await snapshot_genome(
        pool=pool,
        agent_id=agent_id,
        workspace_id=workspace_id,
        trigger=VersionTrigger.SKILL_CREATED,
        status=VersionStatus.CANDIDATE,
        created_by=None,
    )

    assert version_id is not None
    conn.execute.assert_called_once()
    insert_args = conn.execute.call_args.args
    # Check the status argument is 'candidate'
    assert "candidate" in insert_args, f"Expected 'candidate' in INSERT args, got {insert_args}"


@pytest.mark.asyncio
async def test_snapshot_genome_includes_active_skills_in_genome_meta():
    """should embed active skill ids and names into config_snapshot._genome"""
    from flow.application.genome_service import snapshot_genome
    from flow.domain.genome import VersionStatus, VersionTrigger

    agent_id = uuid4()
    workspace_id = uuid4()
    skill_id = uuid4()

    pool = AsyncMock()
    conn = AsyncMock()
    agent_row = {"config": {}, "template": "deer_flow"}
    skill_row = MagicMock()
    skill_row.__getitem__ = lambda self, k: {"id": skill_id, "name": "summarizer"}[k]

    conn.fetchrow = AsyncMock(return_value=agent_row)
    conn.fetch = AsyncMock(return_value=[skill_row])
    conn.execute = AsyncMock()

    ctx_mgr = AsyncMock()
    ctx_mgr.__aenter__ = AsyncMock(return_value=conn)
    ctx_mgr.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=ctx_mgr)

    await snapshot_genome(
        pool=pool,
        agent_id=agent_id,
        workspace_id=workspace_id,
        trigger=VersionTrigger.SKILL_CREATED,
        status=VersionStatus.CANDIDATE,
    )

    insert_args = conn.execute.call_args.args
    # args: (sql, version_id, agent_id, label, config_snapshot, template, ...)
    config_snapshot = insert_args[4]
    assert "_genome" in config_snapshot
    assert str(skill_id) in config_snapshot["_genome"]["active_skill_ids"]
    assert "summarizer" in config_snapshot["_genome"]["active_skill_names"]


@pytest.mark.asyncio
async def test_create_genome_proposal_links_to_candidate_version():
    """should insert a proposal and link it to the candidate version via proposal_id"""
    from flow.application.genome_service import _create_genome_proposal

    workspace_id = uuid4()
    user_id = uuid4()
    candidate_id = uuid4()

    pool = AsyncMock()
    conn = AsyncMock()
    conn.execute = AsyncMock()

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)

    ctx_mgr = AsyncMock()
    ctx_mgr.__aenter__ = AsyncMock(return_value=conn)
    ctx_mgr.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=ctx_mgr)

    proposal_id = await _create_genome_proposal(
        pool=pool,
        workspace_id=workspace_id,
        user_id=user_id,
        candidate_version_id=candidate_id,
        title="New skill learned: summarizer",
        body="Grade 5/5. Approve to promote.",
    )

    assert proposal_id is not None
    assert conn.execute.call_count == 2  # INSERT proposals + UPDATE agent_versions
    update_call = conn.execute.call_args_list[1]
    assert str(proposal_id) in str(update_call) or proposal_id in update_call.args


@pytest.mark.asyncio
async def test_create_genome_proposal_raises_without_user_id():
    """should raise ValueError when user_id is None"""
    from flow.application.genome_service import _create_genome_proposal

    with pytest.raises(ValueError, match="no user_id"):
        await _create_genome_proposal(
            pool=AsyncMock(),
            workspace_id=uuid4(),
            user_id=None,
            candidate_version_id=uuid4(),
            title="t",
            body="b",
        )
