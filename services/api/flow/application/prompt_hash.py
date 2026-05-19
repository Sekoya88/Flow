"""Byte-stable system prompt hashing.

The hash is a deterministic SHA-256 over the *exact* bytes that will be sent
as the genome system prompt. If two runs produce the same hash, the Anthropic /
OpenAI prefix cache will hit, cutting cost and latency.

Drift is detected by comparing the hash of the prompt about to be sent against
the hash stored on the active agent_versions row. A mismatch means something
(template, config, environment) is mutating the prompt between runs.
"""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID

import asyncpg

from flow.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


def compute_prompt_hash(system_prompt: Any) -> str:
    """Compute SHA-256 of the system prompt's canonical text form.

    Accepts a raw string OR an Anthropic content-block list (the
    `cache_control` wrapper used by agent_factory) and reduces both to the
    same canonical bytes — so wrapping for caching does not change the hash.
    """
    if system_prompt is None:
        return ""
    if isinstance(system_prompt, str):
        text = system_prompt
    elif isinstance(system_prompt, list):
        parts: list[str] = []
        for block in system_prompt:
            if isinstance(block, dict):
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        text = "\n".join(parts)
    else:
        # Best-effort fallback for SystemMessage / dict / object types
        content = getattr(system_prompt, "content", None)
        if content is None and isinstance(system_prompt, dict):
            content = system_prompt.get("content")
        text = str(content if content is not None else system_prompt)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def record_prompt_hash(
    pool: asyncpg.Pool,
    *,
    agent_id: UUID,
    prompt_hash: str,
) -> None:
    """Persist the hash on the active genome row. Log drift if it changed.

    First-write wins: the active version's hash is set once; subsequent runs
    are compared. Mismatch -> WARN log (does NOT block execution).
    """
    if not prompt_hash:
        return
    row = await pool.fetchrow(
        """
        SELECT id, prompt_hash
        FROM agent_versions
        WHERE agent_id = $1 AND status = 'active'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        agent_id,
    )
    if row is None:
        return
    stored = row["prompt_hash"]
    if stored is None:
        await pool.execute(
            "UPDATE agent_versions SET prompt_hash = $1 WHERE id = $2",
            prompt_hash,
            row["id"],
        )
        logger.info(
            "prompt_hash.recorded",
            agent_id=str(agent_id),
            agent_version_id=str(row["id"]),
            prompt_hash=prompt_hash,
        )
        return
    if stored != prompt_hash:
        logger.warning(
            "prompt_hash.drift",
            agent_id=str(agent_id),
            agent_version_id=str(row["id"]),
            stored=stored,
            current=prompt_hash,
        )
