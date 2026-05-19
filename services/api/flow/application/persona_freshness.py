"""Persona freshness watcher.

Marks user_personas as stale when the user has active preferences updated
after the persona was last regenerated. Sets derived_from.stale_since = now()
so the UI can surface a "Regenerate" nudge.

Idempotent: already-stale personas are skipped; a persona regenerated after
being flagged will have stale_since removed on next regenerate (regenerate_persona
overwrites derived_from via the INSERT ... ON CONFLICT DO UPDATE path).
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import asyncpg

logger = logging.getLogger(__name__)


async def mark_stale_personas(pool: asyncpg.Pool) -> int:
    """Flag personas where the user has newer active preferences.

    For each (workspace_id, user_id) persona, if any active user_preference
    has last_reinforced_at > persona.updated_at, we write stale_since into
    derived_from.

    Returns the number of personas newly flagged.
    """
    # Fetch all personas not already stale
    personas = await pool.fetch(
        """
        SELECT id, workspace_id, user_id, updated_at, derived_from
        FROM user_personas
        WHERE (derived_from->>'stale_since') IS NULL
        """
    )

    flagged = 0
    now_iso = datetime.now(tz=UTC).isoformat()

    for row in personas:
        workspace_id = row["workspace_id"]
        user_id = row["user_id"]
        persona_updated_at = row["updated_at"]

        # Check if any active preference is newer than persona
        newer_pref = await pool.fetchrow(
            """
            SELECT 1 FROM user_preferences
            WHERE workspace_id = $1
              AND user_id       = $2
              AND status        = 'active'
              AND last_reinforced_at > $3
            LIMIT 1
            """,
            workspace_id,
            user_id,
            persona_updated_at,
        )

        if newer_pref is None:
            continue

        # Merge stale_since into derived_from without overwriting other fields
        patch = json.dumps({"stale_since": now_iso})
        await pool.execute(
            """
            UPDATE user_personas
            SET derived_from = derived_from || $1::jsonb
            WHERE id = $2
            """,
            patch,
            row["id"],
        )
        flagged += 1

    logger.info("persona_freshness.mark_stale_personas flagged=%d", flagged)
    return flagged


async def persona_freshness_tick(ctx: dict) -> None:
    """ARQ cron entry-point — runs daily at 3:30 AM UTC."""
    pool: asyncpg.Pool = ctx["pool"]
    flagged = await mark_stale_personas(pool)
    try:
        import structlog
        structlog.get_logger().info("cron.persona_freshness_tick.done", flagged=flagged)
    except Exception:
        logger.info("cron.persona_freshness_tick.done flagged=%d", flagged)
