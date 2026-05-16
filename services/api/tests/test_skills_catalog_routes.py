"""Contract tests for the Skills Hub additions: catalog, activate, test stream."""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from flow.infrastructure.auth.jwt_utils import create_access_token
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_repo
from flow.interfaces.http.main import create_app

_SECRET = "s" * 32
_USER_ID = uuid4()
_WS_ID = uuid4()
_AGENT_ID = uuid4()
_SKILL_ID = uuid4()


def _auth() -> dict:
    return {"Authorization": f"Bearer {create_access_token(secret=_SECRET, sub=_USER_ID)}"}


def _catalog_row() -> dict:
    ts = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    return {
        "id": _SKILL_ID,
        "agent_id": _AGENT_ID,
        "workspace_id": _WS_ID,
        "name": "structured-research-report",
        "version": 2,
        "content_md": (
            "---\n"
            "name: structured-research-report\n"
            "description: Generate a structured research report\n"
            "version: '1.2'\n"
            "triggers:\n  - research report\n  - market analysis\n"
            "---\n\n"
            "# Body\nDo a thing."
        ),
        "description": "",
        "allowed_tools": [],
        "triggers": [],
        "metadata": {},
        "active": True,
        "score": 0.95,
        "use_count": 3,
        "created_at": ts,
        "agent_name": "Research Analyst",
    }


def _make_repo() -> FlowRepository:
    repo = MagicMock(spec=FlowRepository)
    repo.list_workspaces_for_user = AsyncMock(return_value=[{"id": _WS_ID, "name": "ws"}])
    repo.list_skills_catalog = AsyncMock(return_value=[_catalog_row()])

    activated = {**_catalog_row(), "active": True}
    repo.activate_skill_version = AsyncMock(return_value=activated)
    repo.get_skill_by_id = AsyncMock(return_value=_catalog_row())
    return repo


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLOW_JWT_SECRET", _SECRET)
    from flow import config as cfg
    cfg.get_settings.cache_clear()
    _app = create_app()
    _app.dependency_overrides[get_repo] = _make_repo
    return _app


# ── /catalog ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_catalog_returns_cross_agent_skills_with_agent_name(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            f"/api/v1/skills/catalog?workspace_id={_WS_ID}",
            headers=_auth(),
        )
    assert r.status_code == 200
    data = r.json()
    assert len(data["skills"]) == 1
    s = data["skills"][0]
    assert s["name"] == "structured-research-report"
    assert s["agent_name"] == "Research Analyst"
    assert "research report" in s["triggers"]
    assert s["score"] == 0.95


@pytest.mark.asyncio
async def test_catalog_rejects_other_workspace(app):
    other_ws = uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            f"/api/v1/skills/catalog?workspace_id={other_ws}",
            headers=_auth(),
        )
    assert r.status_code == 403


# ── /activate ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_activate_returns_active_row(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(f"/api/v1/skills/{_SKILL_ID}/activate", headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert data["active"] is True
    assert data["name"] == "structured-research-report"


@pytest.mark.asyncio
async def test_activate_unknown_returns_404(app):
    _app = app
    repo = _make_repo()
    repo.activate_skill_version = AsyncMock(return_value=None)
    _app.dependency_overrides[get_repo] = lambda: repo
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as c:
        r = await c.post(f"/api/v1/skills/{uuid4()}/activate", headers=_auth())
    assert r.status_code == 404


# ── /test (SSE stream) ──────────────────────────────────────────────────────


class _FakeLLM:
    """Async-stream a fixed token sequence (Anthropic-style content fields)."""

    async def astream(self, _messages):
        for tok in ["Hello", " world", "!"]:
            yield MagicMock(content=tok)


@pytest.mark.asyncio
async def test_test_endpoint_streams_tokens(app, monkeypatch):
    # Patch the LLM builder so we don't need real API keys.
    from flow.application import skill_playground
    monkeypatch.setattr(skill_playground, "_build_skill_llm", lambda _s: _FakeLLM())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        async with c.stream(
            "POST",
            f"/api/v1/skills/{_SKILL_ID}/test",
            headers=_auth(),
            json={"prompt": "summarize Q4 results"},
        ) as r:
            assert r.status_code == 200
            chunks = []
            async for raw in r.aiter_text():
                chunks.append(raw)

    body = "".join(chunks)
    assert '"token": "Hello"' in body
    assert '"token": " world"' in body
    assert '"token": "!"' in body
    assert '"done": true' in body


@pytest.mark.asyncio
async def test_test_endpoint_returns_404_when_skill_missing(app):
    _app = app
    repo = _make_repo()
    repo.get_skill_by_id = AsyncMock(return_value=None)
    _app.dependency_overrides[get_repo] = lambda: repo
    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as c:
        r = await c.post(
            f"/api/v1/skills/{uuid4()}/test",
            headers=_auth(),
            json={"prompt": "hi"},
        )
    assert r.status_code == 404
