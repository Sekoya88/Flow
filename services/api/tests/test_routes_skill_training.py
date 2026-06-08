"""Tests for skill training API endpoints (POST /train, GET /training-runs, GET /training-runs/{run_id})."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from flow.infrastructure.auth.jwt_utils import create_access_token
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_repo
from flow.interfaces.http.main import create_app

_SECRET = "c" * 32
_USER_ID = uuid4()
_SKILL_ID = uuid4()
_RUN_ID = uuid4()
_TS = datetime.datetime(2025, 6, 1, 12, 0, 0, tzinfo=datetime.UTC)


def _auth() -> dict:
    token = create_access_token(secret=_SECRET, sub=_USER_ID)
    return {"Authorization": f"Bearer {token}"}


def _make_repo_mock() -> MagicMock:
    repo = MagicMock(spec=FlowRepository)
    repo.create_training_run = AsyncMock(return_value=_RUN_ID)
    repo.list_training_runs = AsyncMock(return_value=[])
    repo.get_training_run = AsyncMock(return_value=None)
    repo.list_training_epochs = AsyncMock(return_value=[])
    repo.list_run_patches = AsyncMock(return_value=[])
    repo.get_skill_content = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLOW_JWT_SECRET", _SECRET)
    from flow import config as cfg

    cfg.get_settings.cache_clear()

    _app = create_app()
    repo = _make_repo_mock()
    _app.dependency_overrides[get_repo] = lambda: repo
    return _app


# ---------------------------------------------------------------------------
# POST /{skill_id}/train
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_training_returns_pending(app):
    """POST /train should return run_id, skill_id, and status=pending."""
    arq_mock = MagicMock()
    arq_mock.enqueue_job = AsyncMock()

    with patch("flow.infrastructure.queue.client.get_arq_pool", AsyncMock(return_value=arq_mock)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                f"/api/v1/skills/{_SKILL_ID}/train",
                headers=_auth(),
                json={
                    "agent_id": str(uuid4()),
                    "workspace_id": str(uuid4()),
                },
            )

    assert r.status_code == 200
    data = r.json()
    assert data["run_id"] == str(_RUN_ID)
    assert data["skill_id"] == str(_SKILL_ID)
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_start_training_enqueues_job(app):
    """POST /train should call enqueue_job with correct function name."""
    arq_mock = MagicMock()
    arq_mock.enqueue_job = AsyncMock()

    agent_id = uuid4()
    workspace_id = uuid4()

    with patch("flow.infrastructure.queue.client.get_arq_pool", AsyncMock(return_value=arq_mock)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post(
                f"/api/v1/skills/{_SKILL_ID}/train",
                headers=_auth(),
                json={
                    "agent_id": str(agent_id),
                    "workspace_id": str(workspace_id),
                    "edit_budget": 8,
                    "max_epochs": 5,
                },
            )

    arq_mock.enqueue_job.assert_awaited_once()
    call_args = arq_mock.enqueue_job.call_args[0]
    assert call_args[0] == "run_skill_training"
    # config dict is last positional arg
    config = call_args[-1]
    assert config["edit_budget"] == 8
    assert config["max_epochs"] == 5


@pytest.mark.asyncio
async def test_start_training_requires_auth(app):
    arq_mock = MagicMock()
    arq_mock.enqueue_job = AsyncMock()

    with patch("flow.infrastructure.queue.client.get_arq_pool", AsyncMock(return_value=arq_mock)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                f"/api/v1/skills/{_SKILL_ID}/train",
                json={"agent_id": str(uuid4()), "workspace_id": str(uuid4())},
            )

    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /{skill_id}/training-runs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_training_runs_returns_empty_list(app):
    """GET /training-runs should return empty runs list when no runs exist."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/v1/skills/{_SKILL_ID}/training-runs", headers=_auth())

    assert r.status_code == 200
    data = r.json()
    assert "runs" in data
    assert data["runs"] == []


@pytest.mark.asyncio
async def test_list_training_runs_returns_runs(app):
    """GET /training-runs should return serialised TrainingRunOut entries."""
    run_row = MagicMock()
    run_row.__getitem__ = lambda self, k: {
        "id": _RUN_ID,
        "status": "completed",
        "epoch": 2,
        "baseline_score": 0.65,
        "best_score": 0.82,
        "accepted": True,
        "created_at": _TS,
        "error_message": None,
    }[k]

    repo = _make_repo_mock()
    repo.list_training_runs = AsyncMock(return_value=[run_row])
    app.dependency_overrides[get_repo] = lambda: repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/v1/skills/{_SKILL_ID}/training-runs", headers=_auth())

    assert r.status_code == 200
    runs = r.json()["runs"]
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    assert runs[0]["epoch"] == 2
    assert runs[0]["accepted"] is True


@pytest.mark.asyncio
async def test_list_training_runs_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/v1/skills/{_SKILL_ID}/training-runs")

    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /{skill_id}/training-runs/{run_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_training_run_404_when_not_found(app):
    """GET /training-runs/{run_id} should return 404 when run does not exist."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            f"/api/v1/skills/{_SKILL_ID}/training-runs/{uuid4()}",
            headers=_auth(),
        )

    assert r.status_code == 404
    assert r.json()["detail"] == "Training run not found"


@pytest.mark.asyncio
async def test_get_training_run_detail_returns_run_with_epochs(app):
    """GET /training-runs/{run_id} should return detail with epoch list."""

    def _row(**kw):
        m = MagicMock()
        m.__getitem__ = lambda self, k: kw[k]
        return m

    run_row = _row(
        id=_RUN_ID,
        status="completed",
        epoch=1,
        baseline_score=0.60,
        best_score=0.75,
        accepted=True,
        created_at=_TS,
        error_message=None,
    )
    epoch_row = _row(
        epoch=1,
        eval_score=0.75,
        baseline_score=0.60,
        accepted=True,
        patch_count=3,
        candidate_skill_id=None,
        item_scores=None,
        created_at=_TS,
    )

    patch_rows = [
        {"patch_json": {"op": "replace", "target": f"## S{i}", "content": "x", "impact_score": 0.8}, "applied": True, "rejected": False}
        for i in range(3)
    ]

    repo = _make_repo_mock()
    repo.get_training_run = AsyncMock(return_value=run_row)
    repo.list_training_epochs = AsyncMock(return_value=[epoch_row])
    repo.list_run_patches = AsyncMock(return_value=patch_rows)
    app.dependency_overrides[get_repo] = lambda: repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            f"/api/v1/skills/{_SKILL_ID}/training-runs/{_RUN_ID}",
            headers=_auth(),
        )

    assert r.status_code == 200
    data = r.json()
    assert data["id"] == str(_RUN_ID)
    assert data["status"] == "completed"
    assert len(data["epochs"]) == 1
    assert data["epochs"][0]["patch_count"] == 3
    assert data["patches_applied"] == 3
    assert data["patches_rejected"] == 0


@pytest.mark.asyncio
async def test_get_training_run_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/v1/skills/{_SKILL_ID}/training-runs/{_RUN_ID}")

    assert r.status_code == 401
