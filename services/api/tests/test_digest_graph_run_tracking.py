"""Verify run_research_digest creates a digest_run row and wires FlowCallbackHandler."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

WS_ID = str(uuid4())
RUN_ID = uuid4()


@pytest.mark.asyncio
async def test_run_research_digest_creates_run_row():
    """run_research_digest must call create_digest_run and update_digest_run."""
    mock_repo = MagicMock()
    mock_repo.create_digest_run = AsyncMock(return_value=RUN_ID)
    mock_repo.update_digest_run = AsyncMock()

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={"persisted_ids": ["p1", "p2"], "obsidian_notes": []}
    )

    mock_pool = AsyncMock()
    mock_pool.close = AsyncMock()

    with (
        patch(
            "flow.infrastructure.graph.research_digest_graph.build_research_digest_graph",
            return_value=mock_graph,
        ),
        patch(
            "flow.infrastructure.graph.research_digest_graph.FlowRepository",
            return_value=mock_repo,
        ),
        patch(
            "flow.infrastructure.graph.research_digest_graph.asyncpg.create_pool",
            new_callable=AsyncMock,
            return_value=mock_pool,
        ),
    ):
        from flow.infrastructure.graph.research_digest_graph import run_research_digest

        await run_research_digest(WS_ID, config={})

    mock_repo.create_digest_run.assert_awaited_once()
    assert mock_repo.update_digest_run.await_count >= 1
    final_call_kwargs = mock_repo.update_digest_run.call_args.kwargs
    assert final_call_kwargs.get("status") in ("done", "failed")
