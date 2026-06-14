"""Tests for the metacog → proposal loop (file_mutation_proposal)."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from flow.application.metacog_service import MetaCogService, Mutation


class _FakePool:
    def __init__(self, *, recent_count=0, owner=True):
        self._recent_count = recent_count
        self._owner = owner
        self.inserts: list[tuple] = []

    async def fetchval(self, query, *args):
        return self._recent_count

    async def fetchrow(self, query, *args):
        return {"user_id": uuid4()} if self._owner else None

    async def execute(self, query, *args):
        self.inserts.append((query, args))


def _mut(conf: float, desc="rewrite prompt") -> Mutation:
    return Mutation(mutation_type="prompt_rewrite", target="system_prompt", description=desc, confidence=conf)


@pytest.mark.asyncio
async def test_files_proposal_for_strong_mutations() -> None:
    pool = _FakePool()
    svc = MetaCogService(pool)
    pid = await svc.file_mutation_proposal(uuid4(), uuid4(), [_mut(0.8)], grade=1)
    assert pid is not None
    assert len(pool.inserts) == 1
    # Body is structured JSON the proposals UI / approval flow can parse.
    body = pool.inserts[0][1][4]
    parsed = json.loads(body)
    assert parsed["kind"] == "metacog_mutation"
    assert len(parsed["mutations"]) == 1


@pytest.mark.asyncio
async def test_skips_low_confidence_mutations() -> None:
    pool = _FakePool()
    svc = MetaCogService(pool)
    pid = await svc.file_mutation_proposal(uuid4(), uuid4(), [_mut(0.3)], grade=2)
    assert pid is None
    assert pool.inserts == []


@pytest.mark.asyncio
async def test_rate_limited_when_recent_proposal_exists() -> None:
    pool = _FakePool(recent_count=1)
    svc = MetaCogService(pool)
    pid = await svc.file_mutation_proposal(uuid4(), uuid4(), [_mut(0.9)], grade=1)
    assert pid is None
    assert pool.inserts == []


@pytest.mark.asyncio
async def test_no_proposal_without_workspace_owner() -> None:
    pool = _FakePool(owner=False)
    svc = MetaCogService(pool)
    pid = await svc.file_mutation_proposal(uuid4(), uuid4(), [_mut(0.9)], grade=1)
    assert pid is None


@pytest.mark.asyncio
async def test_only_strong_mutations_included_in_body() -> None:
    pool = _FakePool()
    svc = MetaCogService(pool)
    await svc.file_mutation_proposal(uuid4(), uuid4(), [_mut(0.9, "strong"), _mut(0.2, "weak")], grade=1)
    parsed = json.loads(pool.inserts[0][1][4])
    descs = {m["description"] for m in parsed["mutations"]}
    assert descs == {"strong"}
