"""Tests for persona_service: template fallback + LLM path + middleware injection."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

# ── synthesize_persona ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_synthesize_falls_back_to_template_when_no_llm():
    from flow.application.persona_service import synthesize_persona
    facets = [
        {"class": "style", "value": "concise"},
        {"class": "tooling", "value": "python"},
        {"class": "veto", "value": "no emojis"},
        {"class": "domain", "value": "ML"},
    ]
    out = await synthesize_persona(llm=None, facets=facets, cv_text=None)
    assert "# Identity" in out
    assert "ML" in out
    assert "concise" in out
    assert "no emojis" in out


@pytest.mark.asyncio
async def test_synthesize_falls_back_when_facets_empty_even_with_llm():
    from flow.application.persona_service import synthesize_persona
    llm = MagicMock()
    llm.ainvoke = AsyncMock()  # should NOT be called
    out = await synthesize_persona(llm=llm, facets=[], cv_text=None)
    assert "(unspecified)" in out
    llm.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_synthesize_uses_llm_response_when_available():
    from flow.application.persona_service import synthesize_persona
    expected = "# Identity\nYou work with a senior engineer.\n"
    llm = MagicMock()
    response = MagicMock()
    response.content = expected
    llm.ainvoke = AsyncMock(return_value=response)
    facets = [{"class": "style", "value": "concise"}]
    out = await synthesize_persona(llm=llm, facets=facets, cv_text=None)
    assert out == expected.strip()


@pytest.mark.asyncio
async def test_synthesize_handles_anthropic_block_list_content():
    from flow.application.persona_service import synthesize_persona
    llm = MagicMock()
    response = MagicMock()
    response.content = [{"type": "text", "text": "# Identity\nblock A"}, "block B"]
    llm.ainvoke = AsyncMock(return_value=response)
    out = await synthesize_persona(llm=llm, facets=[{"class": "style", "value": "x"}], cv_text=None)
    assert "block A" in out
    assert "block B" in out


@pytest.mark.asyncio
async def test_synthesize_falls_back_on_llm_exception():
    from flow.application.persona_service import synthesize_persona
    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=RuntimeError("network down"))
    facets = [{"class": "domain", "value": "data"}]
    out = await synthesize_persona(llm=llm, facets=facets, cv_text=None)
    assert "# Identity" in out
    assert "data" in out


# ── regenerate_persona (asyncpg pool mock) ────────────────────────────────────


@pytest.mark.asyncio
async def test_regenerate_persona_upserts_and_returns_row():
    from flow.application import persona_service
    workspace_id = uuid4()
    user_id = uuid4()

    facet_rows = [
        {"class": "style", "value": "concise", "status": "active", "score": 0.9},
        {"class": "tooling", "value": "python", "status": "active", "score": 0.8},
    ]
    now = datetime.now(UTC)
    upsert_row = {
        "id": uuid4(),
        "workspace_id": workspace_id,
        "user_id": user_id,
        "content_md": "# Identity\nfoo",
        "version": 1,
        "derived_from": '{"preferences": 2, "llm": false, "manual": false}',
        "created_at": now,
        "updated_at": now,
    }
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=facet_rows)
    pool.fetchrow = AsyncMock(return_value=upsert_row)

    settings = MagicMock(anthropic_api_key=None, openai_api_key=None)
    out = await persona_service.regenerate_persona(pool, workspace_id, user_id, settings)

    assert out["content_md"] == "# Identity\nfoo"
    pool.fetch.assert_awaited_once()
    pool.fetchrow.assert_awaited_once()


# ── FlowPersonaMiddleware ─────────────────────────────────────────────────────


def _make_runtime():
    from flow.infrastructure.llm.middleware.base import HarnessRuntime
    return HarnessRuntime(
        workspace_id=uuid4(), agent_id=uuid4(),
        user_id=uuid4(), execution_id=uuid4(), thread_id="t1",
    )


@pytest.mark.asyncio
async def test_persona_middleware_prepends_system_message_when_row_exists():
    from flow.infrastructure.llm.middleware.persona import FlowPersonaMiddleware
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value={"content_md": "# Identity\nYou work with X."})
    mw = FlowPersonaMiddleware(pool=pool)
    state = {"messages": [HumanMessage(content="hello")]}
    result = await mw.before_agent(state, _make_runtime())
    assert isinstance(result["messages"][0], SystemMessage)
    assert "About the user" in result["messages"][0].content
    assert "# Identity" in result["messages"][0].content


@pytest.mark.asyncio
async def test_persona_middleware_noop_when_no_row():
    from flow.infrastructure.llm.middleware.persona import FlowPersonaMiddleware
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=None)
    mw = FlowPersonaMiddleware(pool=pool)
    state = {"messages": [HumanMessage(content="hi")]}
    result = await mw.before_agent(state, _make_runtime())
    assert result is state


@pytest.mark.asyncio
async def test_persona_middleware_noop_when_content_empty():
    from flow.infrastructure.llm.middleware.persona import FlowPersonaMiddleware
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value={"content_md": "   \n  "})
    mw = FlowPersonaMiddleware(pool=pool)
    state = {"messages": [HumanMessage(content="hi")]}
    result = await mw.before_agent(state, _make_runtime())
    assert result is state


@pytest.mark.asyncio
async def test_persona_middleware_noop_when_pool_none():
    from flow.infrastructure.llm.middleware.persona import FlowPersonaMiddleware
    mw = FlowPersonaMiddleware(pool=None)
    state = {"messages": [HumanMessage(content="hi")]}
    result = await mw.before_agent(state, _make_runtime())
    assert result is state


@pytest.mark.asyncio
async def test_persona_middleware_swallows_db_error():
    from flow.infrastructure.llm.middleware.persona import FlowPersonaMiddleware
    pool = MagicMock()
    pool.fetchrow = AsyncMock(side_effect=RuntimeError("connection lost"))
    mw = FlowPersonaMiddleware(pool=pool)
    state = {"messages": [HumanMessage(content="hi")]}
    result = await mw.before_agent(state, _make_runtime())
    # Failure must not block agent execution
    assert result is state
