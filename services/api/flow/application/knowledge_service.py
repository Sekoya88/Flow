from __future__ import annotations

import asyncio
from uuid import UUID

from flow.config import Settings
from flow.infrastructure.llm import embeddings as emb_svc
from flow.infrastructure.observability.logging import get_logger
from flow.infrastructure.persistence.repo import FlowRepository

logger = get_logger(__name__)


def chunk_text(body: str, max_chars: int = 1400) -> list[str]:
    parts = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not parts:
        return [body.strip()[:max_chars]] if body.strip() else []
    chunks: list[str] = []
    buf = ""
    for p in parts:
        if len(buf) + len(p) + 2 > max_chars and buf:
            chunks.append(buf.strip())
            buf = p
        else:
            buf = (buf + "\n\n" + p).strip() if buf else p
    if buf:
        chunks.append(buf.strip())
    return chunks[:80]


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
