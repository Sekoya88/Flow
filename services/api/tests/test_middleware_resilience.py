"""Tests for FlowResilienceMiddleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


def _make_runtime():
    from flow.infrastructure.llm.middleware.base import HarnessRuntime

    return HarnessRuntime(
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        execution_id=uuid4(),
        thread_id="t1",
    )


def _make_fake_llm():
    """Minimal duck-typed LLM with _agenerate for patching."""
    llm = MagicMock()
    llm._agenerate = AsyncMock()
    return llm


@pytest.mark.asyncio
async def test_patch_llm_adds_retry_to_agenerate():
    from flow.infrastructure.llm.middleware.resilience import FlowResilienceMiddleware

    llm = _make_fake_llm()
    original = llm._agenerate
    mw = FlowResilienceMiddleware(model_retry=3)
    mw.patch_llm(llm)
    # _agenerate should have been replaced
    assert llm._agenerate is not original


@pytest.mark.asyncio
async def test_patch_llm_retries_on_rate_limit():
    from openai import RateLimitError

    from flow.infrastructure.llm.middleware.resilience import FlowResilienceMiddleware

    call_count = 0
    fake_response = MagicMock()

    async def flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RateLimitError("rate limit", response=MagicMock(status_code=429), body={})
        return fake_response

    llm = _make_fake_llm()
    llm._agenerate = flaky
    mw = FlowResilienceMiddleware(model_retry=3, min_wait=0, max_wait=0)
    mw.patch_llm(llm)
    result = await llm._agenerate([])
    assert result is fake_response
    assert call_count == 3


@pytest.mark.asyncio
async def test_patch_llm_raises_after_exhaustion():
    from openai import RateLimitError

    from flow.infrastructure.llm.middleware.resilience import FlowResilienceMiddleware

    call_count = 0

    async def always_fail(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise RateLimitError("rate limit", response=MagicMock(status_code=429), body={})

    llm = _make_fake_llm()
    llm._agenerate = always_fail
    mw = FlowResilienceMiddleware(model_retry=2, min_wait=0, max_wait=0)
    mw.patch_llm(llm)
    with pytest.raises(RateLimitError):
        await llm._agenerate([])
    assert call_count == 2  # exhausted all retries before raising


@pytest.mark.asyncio
async def test_wrap_tool_call_retries_on_error():
    from flow.infrastructure.llm.middleware.resilience import FlowResilienceMiddleware

    call_count = 0

    async def flaky_tool(args):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ConnectionError("tool flaked")
        return "ok"

    mw = FlowResilienceMiddleware(tool_retry=2, min_wait=0, max_wait=0)
    result = await mw.wrap_tool_call(flaky_tool, {})
    assert result == "ok"
    assert call_count == 2


@pytest.mark.asyncio
async def test_wrap_tool_call_continues_after_exhaustion():
    from flow.infrastructure.llm.middleware.resilience import FlowResilienceMiddleware

    async def always_fail(args):
        raise ConnectionError("broken")

    mw = FlowResilienceMiddleware(tool_retry=2, min_wait=0, max_wait=0)
    result = await mw.wrap_tool_call(always_fail, {})
    assert result is None  # continued, didn't crash
