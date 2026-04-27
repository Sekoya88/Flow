from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict:
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        return {"status": "degraded", "db": False}
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "ok", "db": True}
    except Exception:
        return {"status": "degraded", "db": False}
