from __future__ import annotations

import asyncpg

from flow.config import Settings


async def create_pool(settings: Settings) -> asyncpg.Pool:
    return await asyncpg.create_pool(settings.database_url, min_size=1, max_size=10)


async def close_pool(pool: asyncpg.Pool | None) -> None:
    if pool:
        await pool.close()
