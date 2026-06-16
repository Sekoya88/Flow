"""Regression test for the episodic-memory bridge in run_deer_execution.

Guards against a positional-arg mismatch bug where `execution_id` was passed
in the `content` slot of `repo.insert_episodic_memory(...)` — every episodic
write silently stored a UUID instead of the Q/A summary string.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from flow.application.execution_runner import run_deer_execution
from flow.config import Settings


class _FakeSnapshot:
    def __init__(self, values: dict) -> None:
        self.values = values


class _FakeGraph:
    def __init__(self, answer: str) -> None:
        self._answer = answer

    async def astream(self, *_args, **_kwargs):
        return
        yield  # pragma: no cover - makes this an async generator

    async def aget_state(self, _config):
        return _FakeSnapshot({"answer": self._answer, "confidence": 0.9, "messages": []})


@pytest.mark.asyncio
async def test_episodic_bridge_stores_summary_not_execution_id():
    execution_id = uuid4()
    workspace_id = uuid4()
    agent_id = uuid4()
    user_id = uuid4()
    user_message = "What is the capital of France?"
    answer = "Paris."

    fake_repo = MagicMock()
    fake_repo.get_thread_id = AsyncMock(return_value=execution_id)
    fake_repo.complete_execution = AsyncMock()
    fake_repo.insert_episodic_memory = AsyncMock()

    fake_pool = MagicMock()
    fake_conn = AsyncMock()
    fake_conn.fetch = AsyncMock(return_value=[])
    fake_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=fake_conn)
    fake_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    fake_stream_hub = MagicMock()
    fake_stream_hub.publish = MagicMock()

    settings = Settings(openai_api_key=None)

    with (
        patch("flow.application.execution_runner.FlowRepository", return_value=fake_repo),
        patch("flow.application.execution_runner.build_agent_from_ctx", return_value=_FakeGraph(answer)),
        patch("flow.application.execution_runner.ExecutionEventEmitter") as _Emitter,
        patch("flow.application.execution_runner._index_execution", new=AsyncMock()),
    ):
        _Emitter.return_value.emit = AsyncMock()

        await run_deer_execution(
            pool=fake_pool,
            settings=settings,
            stream_hub=fake_stream_hub,
            checkpointer=None,
            execution_id=execution_id,
            workspace_id=workspace_id,
            agent_id=agent_id,
            user_id=user_id,
            user_message=user_message,
        )

    fake_repo.insert_episodic_memory.assert_awaited_once()
    call = fake_repo.insert_episodic_memory.await_args
    stored_content = call.args[3]
    assert isinstance(stored_content, str)
    assert stored_content == f"Q: {user_message[:400]}\n\nA: {answer[:800]}"
    assert execution_id not in (call.args[3],)
    assert call.kwargs["execution_id"] == execution_id
