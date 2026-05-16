"""Tests for the in-memory token-bucket rate limiter."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from flow.interfaces.http.rate_limit import RateLimiter, TokenBucket


# ── Unit: TokenBucket ────────────────────────────────────────────────────────

def test_bucket_allows_up_to_capacity():
    bucket = TokenBucket(capacity=3, rate=0)  # rate=0 — no refill
    assert bucket.consume() is True
    assert bucket.consume() is True
    assert bucket.consume() is True
    assert bucket.consume() is False  # bucket empty


def test_bucket_refills_over_time():
    bucket = TokenBucket(capacity=1, rate=10)  # 10 tokens/sec
    bucket.consume()  # drain
    # Simulate 0.2s elapsed → 2 new tokens added → capped at 1
    bucket.last_refill -= 0.2
    assert bucket.consume() is True


def test_bucket_does_not_exceed_capacity():
    bucket = TokenBucket(capacity=2, rate=100)
    bucket.last_refill -= 10  # 10s elapsed → 1000 potential tokens
    bucket.tokens = 0
    bucket.consume()  # triggers refill; tokens should cap at 2 then consume 1
    assert bucket.tokens <= bucket.capacity


# ── Unit: RateLimiter ────────────────────────────────────────────────────────

def test_rate_limiter_allows_within_limit():
    limiter = RateLimiter(requests_per_minute=5)
    uid = uuid4()
    results = [limiter.check(uid, "test") for _ in range(5)]
    assert all(results)


def test_rate_limiter_blocks_above_limit():
    limiter = RateLimiter(requests_per_minute=3)
    uid = uuid4()
    results = [limiter.check(uid, "test") for _ in range(5)]
    assert results[:3] == [True, True, True]
    assert results[3] is False
    assert results[4] is False


def test_rate_limiter_different_users_independent():
    limiter = RateLimiter(requests_per_minute=2)
    u1, u2 = uuid4(), uuid4()
    # Exhaust u1
    limiter.check(u1, "test")
    limiter.check(u1, "test")
    assert limiter.check(u1, "test") is False
    # u2 unaffected
    assert limiter.check(u2, "test") is True


def test_rate_limiter_different_routes_independent():
    limiter = RateLimiter(requests_per_minute=1)
    uid = uuid4()
    limiter.check(uid, "route_a")
    assert limiter.check(uid, "route_a") is False
    assert limiter.check(uid, "route_b") is True


# ── Integration: skill_test_rate_limit dependency ────────────────────────────

@pytest.mark.asyncio
async def test_skill_test_rate_limit_raises_429():
    from fastapi import HTTPException
    from flow.interfaces.http.rate_limit import skill_test_rate_limit, _skill_test_limiter

    uid = uuid4()
    request = MagicMock()

    # Exhaust the bucket for this user
    with patch.object(_skill_test_limiter, "check", return_value=False):
        with pytest.raises(HTTPException) as exc_info:
            skill_test_rate_limit(request, uid)
        assert exc_info.value.status_code == 429
        assert "Retry-After" in exc_info.value.headers
