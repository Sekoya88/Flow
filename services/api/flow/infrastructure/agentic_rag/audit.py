from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import asyncpg

from flow.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


async def save_rag_audit(
    pool: asyncpg.Pool,
    *,
    execution_id: UUID | None,
    workspace_id: UUID,
    query_original: str,
    query_rewritten: str | None,
    routing_decision: str,
    iteration_count: int,
    fallback_used: bool,
    confidence_score: float | None,
    latency_ms: dict[str, Any],
    explanation: dict[str, Any],
    citations: list[dict[str, Any]],
) -> int | None:
    """Persist retrieval trace. Returns rag_query_history.id or None on failure."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO rag_query_history (
                    execution_id, workspace_id, query_original, query_rewritten,
                    routing_decision, iteration_count, fallback_used,
                    confidence_score, latency_ms, explanation
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10::jsonb)
                RETURNING id
                """,
                execution_id,
                workspace_id,
                query_original,
                query_rewritten,
                routing_decision,
                iteration_count,
                fallback_used,
                confidence_score,
                json.dumps(latency_ms),
                json.dumps(explanation),
            )
            if row is None:
                return None
            qid = int(row["id"])
            for cit in citations:
                await conn.execute(
                    """
                    INSERT INTO rag_citations (
                        query_history_id, chunk_id, source_url, source_title,
                        page_number, excerpt, relevance_score, used_in_answer
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    qid,
                    cit.get("chunk_id", ""),
                    cit.get("source_url") or "",
                    cit.get("source_title") or "",
                    cit.get("page_number"),
                    (cit.get("excerpt") or "")[:200],
                    cit.get("relevance_score"),
                    bool(cit.get("used_in_answer", False)),
                )
            return qid
    except Exception:
        logger.exception("rag_audit.save_failed")
        return None
