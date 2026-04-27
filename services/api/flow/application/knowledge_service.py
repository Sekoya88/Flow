from __future__ import annotations

from uuid import UUID

from flow.infrastructure.llm import embeddings as emb_svc
from flow.infrastructure.persistence.repo import FlowRepository


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
) -> UUID:
    source_id = await repo.insert_knowledge_source(
        workspace_id, title, body, ingest_status="processing"
    )
    try:
        chunks = chunk_text(body)
        if not chunks:
            await repo.set_knowledge_ingest(source_id, "indexed", None)
            return source_id
        embs = await emb_svc.embed_texts(api_key=openai_api_key, texts=chunks)
        for i, (content, emb) in enumerate(zip(chunks, embs, strict=True)):
            await repo.insert_chunk(source_id, i, content, emb)
        await repo.set_knowledge_ingest(source_id, "indexed", None)
        return source_id
    except Exception as exc:
        await repo.set_knowledge_ingest(source_id, "failed", str(exc)[:2000])
        raise
