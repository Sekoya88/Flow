from __future__ import annotations

import json

import asyncpg

from flow.config import Settings


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def create_pool(settings: Settings) -> asyncpg.Pool:
    return await asyncpg.create_pool(settings.database_url, min_size=1, max_size=10, init=_init_connection)


async def close_pool(pool: asyncpg.Pool | None) -> None:
    if pool:
        await pool.close()
