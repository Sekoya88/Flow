"""In-memory token-bucket rate limiter for FastAPI routes.

Keyed on (user_id, route_key). Each bucket refills at `rate` tokens per second
up to `capacity` tokens. A request costs 1 token; HTTP 429 is returned when
the bucket is empty.

No external dependencies. Not suitable for multi-process deployments —
use Redis-based limiting when horizontally scaled.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from threading import Lock
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request

from flow.interfaces.http.deps import get_current_user_id


class TokenBucket:
    __slots__ = ("tokens", "last_refill", "capacity", "rate")

    def __init__(self, capacity: float, rate: float) -> None:
        self.capacity = capacity
        self.rate = rate  # tokens per second
        self.tokens = capacity
        self.last_refill = time.monotonic()

    def consume(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimiter:
    def __init__(self, requests_per_minute: int = 10) -> None:
        self._rpm = requests_per_minute
        self._rate = requests_per_minute / 60.0
        self._buckets: dict[tuple, TokenBucket] = defaultdict(lambda: TokenBucket(capacity=float(self._rpm), rate=self._rate))
        self._lock = Lock()

    def check(self, user_id: UUID, route_key: str) -> bool:
        key = (str(user_id), route_key)
        with self._lock:
            return self._buckets[key].consume()


# Module-level singleton; capacity/rate configurable via env
_RPM = int(os.environ.get("FLOW_SKILL_TEST_RPM", "10"))
_skill_test_limiter = RateLimiter(requests_per_minute=_RPM)


def skill_test_rate_limit(
    request: Request,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> None:
    """FastAPI dependency — raises HTTP 429 if the user exceeds the limit."""
    if not _skill_test_limiter.check(user_id, "skill_test"):
        retry_after = int(60 / _RPM) + 1
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
