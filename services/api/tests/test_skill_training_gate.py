"""Tests for the dataset-aware, per-item regression gate.

The gate decision (`SkillTrainer._decide_gate`) is a pure function: given baseline
and candidate per-item scores for the SAME golden set, it decides whether a candidate
skill may activate. It must block activation when any single item regresses beyond the
floor, even if the aggregate average improves — this protects safety-critical items
(e.g. the Lucis chest-pain emergency item) from being masked by gains elsewhere.

Plus thin wiring tests: golden_set_id flows route → run row → ARQ payload.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from flow.application.skill_trainer import SkillTrainer, TrainingConfig
from flow.infrastructure.auth.jwt_utils import create_access_token
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_repo
from flow.interfaces.http.main import create_app


def _trainer() -> SkillTrainer:
    return SkillTrainer(pool=None)  # type: ignore[arg-type]


def _items(*scores: float) -> list[dict]:
    """Build per-item score rows keyed by stable item ids 'i0', 'i1', …."""
    return [{"item_id": f"i{idx}", "input_text": f"item {idx}", "score": s} for idx, s in enumerate(scores)]


_CFG = TrainingConfig(min_val_improvement=0.02, regression_floor=0.1)


# ── _decide_gate: blocking on per-item regression ───────────────────────────────


def test_gate_blocks_when_an_item_regresses_beyond_floor_even_if_aggregate_improves():
    trainer = _trainer()
    # Aggregate climbs (0.70 → 0.775) but item i1 collapses 0.90 → 0.60 (Δ -0.30).
    baseline = _items(0.50, 0.90)
    candidate = _items(0.95, 0.60)

    gate = trainer._decide_gate(baseline, candidate, _CFG)

    assert gate.candidate_avg > gate.baseline_avg  # aggregate improved
    assert gate.accepted is False
    assert gate.status == "blocked"
    assert gate.blocked_reason and "item 1" in gate.blocked_reason


def test_gate_accepts_when_aggregate_improves_and_no_item_regresses():
    trainer = _trainer()
    baseline = _items(0.50, 0.60)
    candidate = _items(0.80, 0.70)  # both items up

    gate = trainer._decide_gate(baseline, candidate, _CFG)

    assert gate.accepted is True
    assert gate.status == "accepted"
    assert gate.blocked_reason is None


def test_gate_rejects_when_aggregate_does_not_improve_enough():
    trainer = _trainer()
    baseline = _items(0.70, 0.70)
    candidate = _items(0.71, 0.70)  # +0.005 avg, below min_val_improvement

    gate = trainer._decide_gate(baseline, candidate, _CFG)

    assert gate.accepted is False
    assert gate.status == "rejected"


def test_gate_item_scores_carry_before_after_and_delta():
    trainer = _trainer()
    baseline = _items(0.40, 0.80)
    candidate = _items(0.90, 0.50)

    gate = trainer._decide_gate(baseline, candidate, _CFG)

    assert len(gate.item_scores) == 2
    first = gate.item_scores[0]
    assert set(first) >= {"item_id", "input", "baseline_score", "candidate_score", "delta"}
    assert first["delta"] == pytest.approx(0.50)  # 0.90 - 0.40
    assert gate.item_scores[1]["delta"] == pytest.approx(-0.30)


def test_gate_baseline_avg_computed_only_from_passed_items_not_mixed_history():
    """Baseline must come from the same-set rollout, never a global average."""
    trainer = _trainer()
    baseline = _items(0.20, 0.40, 0.60)  # mean 0.40
    candidate = _items(0.20, 0.40, 0.60)

    gate = trainer._decide_gate(baseline, candidate, _CFG)

    assert gate.baseline_avg == pytest.approx(0.40)
    assert gate.candidate_avg == pytest.approx(0.40)


# ── Wiring: golden_set_id flows through ─────────────────────────────────────────

_SECRET = "c" * 32
_RUN_ID = uuid4()


def _auth() -> dict:
    return {"Authorization": f"Bearer {create_access_token(secret=_SECRET, sub=uuid4())}"}


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLOW_JWT_SECRET", _SECRET)
    from flow import config as cfg

    cfg.get_settings.cache_clear()
    _app = create_app()
    repo = MagicMock(spec=FlowRepository)
    repo.create_training_run = AsyncMock(return_value=_RUN_ID)
    _app.dependency_overrides[get_repo] = lambda: repo
    _app.state._repo = repo  # expose for assertions
    return _app


@pytest.mark.asyncio
async def test_train_forwards_golden_set_id_to_run_and_arq_payload(app):
    arq_mock = MagicMock()
    arq_mock.enqueue_job = AsyncMock()
    skill_id, agent_id, ws_id, set_id = uuid4(), uuid4(), uuid4(), uuid4()

    with patch("flow.infrastructure.queue.client.get_arq_pool", AsyncMock(return_value=arq_mock)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                f"/api/v1/skills/{skill_id}/train",
                headers=_auth(),
                json={
                    "agent_id": str(agent_id),
                    "workspace_id": str(ws_id),
                    "golden_set_id": str(set_id),
                },
            )

    assert r.status_code == 200
    # Stored on the run row…
    app.state._repo.create_training_run.assert_awaited_once()
    assert app.state._repo.create_training_run.call_args.kwargs["golden_set_id"] == set_id
    # …and forwarded in the ARQ job payload (last positional arg is the config dict).
    payload = arq_mock.enqueue_job.call_args[0][-1]
    assert payload["golden_set_id"] == str(set_id)


@pytest.mark.asyncio
async def test_override_activates_blocked_candidate(app):
    """POST /override finds the latest epoch's candidate and activates it."""
    skill_id, run_id, candidate_id = uuid4(), uuid4(), uuid4()
    repo: MagicMock = app.state._repo

    repo.get_training_run = AsyncMock(return_value={"accepted": False})
    repo.list_training_epochs = AsyncMock(
        return_value=[
            {"candidate_skill_id": candidate_id, "accepted": False},
        ]
    )
    repo.activate_skill_version = AsyncMock(return_value={"id": candidate_id})
    repo.update_training_run = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            f"/api/v1/skills/{skill_id}/training-runs/{run_id}/override",
            headers=_auth(),
        )

    assert r.status_code == 200
    body = r.json()
    assert body["activated"] is True
    assert body["skill_version_id"] == str(candidate_id)
    repo.activate_skill_version.assert_awaited_once_with(candidate_id)
    repo.update_training_run.assert_awaited_once_with(run_id, accepted=True)


@pytest.mark.asyncio
async def test_override_is_idempotent_when_already_accepted(app):
    """POST /override on an already-accepted run returns activated=False without re-activating."""
    skill_id, run_id = uuid4(), uuid4()
    repo: MagicMock = app.state._repo

    repo.get_training_run = AsyncMock(return_value={"accepted": True})
    repo.activate_skill_version = AsyncMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            f"/api/v1/skills/{skill_id}/training-runs/{run_id}/override",
            headers=_auth(),
        )

    assert r.status_code == 200
    assert r.json()["activated"] is False
    repo.activate_skill_version.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_training_run_persists_golden_set_id():
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value={"id": _RUN_ID})
    repo = FlowRepository.__new__(FlowRepository)
    repo._pool = pool  # type: ignore[attr-defined]
    set_id = uuid4()

    await repo.create_training_run(
        skill_id=uuid4(),
        agent_id=uuid4(),
        workspace_id=uuid4(),
        edit_budget=5,
        golden_set_id=set_id,
    )

    # golden_set_id must appear among the positional params handed to the INSERT.
    args = pool.fetchrow.call_args[0]
    assert set_id in args
