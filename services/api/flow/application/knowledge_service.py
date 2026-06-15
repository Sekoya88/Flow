from __future__ import annotations

import asyncio
from uuid import UUID

from flow.config import Settings
from flow.infrastructure.llm import embeddings as emb_svc
from flow.infrastructure.observability.logging import get_logger
from flow.infrastructure.persistence.repo import FlowRepository

logger = get_logger(__name__)

_CHUNK_HARD_CAP = 500
_MAX_TOKENS = 400
_OVERLAP_TOKENS = 60  # ~15% overlap


def chunk_text(body: str, max_tokens: int = _MAX_TOKENS, overlap_tokens: int = _OVERLAP_TOKENS) -> list[str]:
    """Token-aware chunker with sliding overlap.

    Uses tiktoken cl100k_base (same tokenizer as text-embedding-3-*). Falls back
    to the old char-split when tiktoken is unavailable so ingest never hard-fails.
    """
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        tokens = enc.encode(body)
        if not tokens:
            return []

        chunks: list[str] = []
        start = 0
        while start < len(tokens):
            end = min(start + max_tokens, len(tokens))
            text = enc.decode(tokens[start:end]).strip()
            if text:
                chunks.append(text)
            if end >= len(tokens):
                break
            start = end - overlap_tokens

        if len(chunks) > _CHUNK_HARD_CAP:
            logger.warning(
                "knowledge.chunk_truncated",
                original=len(chunks),
                kept=_CHUNK_HARD_CAP,
            )
            chunks = chunks[:_CHUNK_HARD_CAP]
        return chunks

    except Exception:
        # Fallback: original paragraph split
        parts = [p.strip() for p in body.split("\n\n") if p.strip()]
        if not parts:
            return [body.strip()[:1400]] if body.strip() else []
        result: list[str] = []
        buf = ""
        for p in parts:
            if len(buf) + len(p) + 2 > 1400 and buf:
                result.append(buf.strip())
                buf = p
            else:
                buf = (buf + "\n\n" + p).strip() if buf else p
        if buf:
            result.append(buf.strip())
        return result[:_CHUNK_HARD_CAP]


async def ingest_document(
    *,
    repo: FlowRepository,
    openai_api_key: str,
    workspace_id: UUID,
    title: str,
    body: str,
    settings: Settings | None = None,
) -> UUID:
    source_id = await repo.insert_knowledge_source(workspace_id, title, body, ingest_status="processing")
    try:
        chunks = chunk_text(body)
        if not chunks:
            await repo.set_knowledge_ingest(source_id, "indexed", None)
            return source_id
        embs = await emb_svc.embed_texts(api_key=openai_api_key, texts=chunks)
        for i, (content, emb) in enumerate(zip(chunks, embs, strict=True)):
            chunk_pk = await repo.insert_chunk(source_id, i, content, emb)
            if settings and settings.qdrant_url and settings.qdrant_url.strip():
                try:
                    from flow.infrastructure.agentic_rag.qdrant_hybrid import (
                        get_qdrant_client,
                        setup_collection,
                        sparse_encode_text,
                        upsert_knowledge_chunk_async,
                    )

                    base = settings.qdrant_url.strip().rstrip("/")
                    url = base if base.startswith("http") else f"http://{base}"
                    client = get_qdrant_client(url)
                    coll = settings.qdrant_collection
                    await asyncio.to_thread(setup_collection, client, coll)
                    si, sv = await sparse_encode_text(content)
                    await upsert_knowledge_chunk_async(
                        client,
                        collection=coll,
                        workspace_id=workspace_id,
                        source_id=source_id,
                        title=title,
                        chunk_pk=chunk_pk,
                        content=content,
                        dense_embedding=emb,
                        sparse_indices=si,
                        sparse_values=sv,
                    )
                except Exception:
                    logger.warning("qdrant.upsert_failed", source_id=str(source_id), chunk_index=i)
        await repo.set_knowledge_ingest(source_id, "indexed", None)
        return source_id
    except Exception as exc:
        await repo.set_knowledge_ingest(source_id, "failed", str(exc)[:2000])
        raise
