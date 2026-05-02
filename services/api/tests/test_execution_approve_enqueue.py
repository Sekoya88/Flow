"""Approve path must enqueue the same arq job name the worker registers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from flow.interfaces.http.routes.executions import approve_execution


@pytest.mark.asyncio
async def test_approve_enqueues_run_deer_execution_with_agent_config(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_arq = MagicMock()
    mock_arq.enqueue_job = AsyncMock()

    async def fake_get_arq_pool() -> MagicMock:
        return mock_arq

    monkeypatch.setattr(
        "flow.infrastructure.queue.client.get_arq_pool",
        fake_get_arq_pool,
    )

    execution_id = uuid4()
    workspace_id = uuid4()
    agent_id = uuid4()
    user_id = uuid4()

    repo = MagicMock()
    repo.get_execution_for_user = AsyncMock(
        return_value={
            "id": execution_id,
            "status": "running",
            "agent_id": agent_id,
            "workspace_id": workspace_id,
            "user_message": "hello",
            "created_at": None,
            "agent_config": {"tools": {"retrieve": True}},
        }
    )

    request = MagicMock()
    chk = AsyncMock()
    chk.aput = AsyncMock()
    request.app.state.checkpointer = chk

    await approve_execution(request, execution_id, user_id, repo)

    mock_arq.enqueue_job.assert_awaited_once()
    call = mock_arq.enqueue_job.await_args
    assert call is not None
    args, _kwargs = call
    assert args[0] == "run_deer_execution"
    assert args[1:6] == (
        str(execution_id),
        str(workspace_id),
        str(agent_id),
        str(user_id),
        "",
    )
    assert args[6] == {"tools": {"retrieve": True}}
