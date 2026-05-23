from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from flow.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)

EMBED_DIM = 1536

_sparse_model = None


def sparse_encode_sync(text: str) -> tuple[list[int], list[float]]:
    global _sparse_model
    if _sparse_model is None:
        from fastembed import SparseTextEmbedding

        _sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    row = list(_sparse_model.embed([text]))[0]
    return row.indices.tolist(), row.values.tolist()


async def sparse_encode_text(text: str) -> tuple[list[int], list[float]]:
    return await asyncio.to_thread(sparse_encode_sync, text)


def qdrant_point_id(workspace_id: UUID, chunk_pk: int) -> str:
    import uuid as _uuid
    # Qdrant accepts only UUID or uint64; generate a deterministic UUID
    return str(_uuid.uuid5(workspace_id, str(chunk_pk)))


def get_qdrant_client(url: str) -> QdrantClient:
    return QdrantClient(url=url)


def setup_collection(client: QdrantClient, collection: str) -> None:
    if client.collection_exists(collection_name=collection):
        return
    client.create_collection(
        collection_name=collection,
        vectors_config={
            "dense": qmodels.VectorParams(size=EMBED_DIM, distance=qmodels.Distance.COSINE),
        },
        sparse_vectors_config={
            "sparse": qmodels.SparseVectorParams(index=qmodels.SparseIndexParams(on_disk=False)),
        },
    )
    client.create_payload_index(
        collection_name=collection,
        field_name="workspace_id",
        field_schema=qmodels.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=collection,
        field_name="source_id",
        field_schema=qmodels.PayloadSchemaType.KEYWORD,
    )
    logger.info("qdrant.collection.created", collection=collection)


def _workspace_filter(workspace_id: UUID) -> qmodels.Filter:
    return qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="workspace_id",
                match=qmodels.MatchValue(value=str(workspace_id)),
            )
        ]
    )


def hybrid_search_rrf(
    client: QdrantClient,
    *,
    collection: str,
    workspace_id: UUID,
    dense_vector: list[float],
    sparse_indices: list[int],
    sparse_values: list[float],
    limit: int = 8,
) -> list[dict[str, Any]]:
    flt = _workspace_filter(workspace_id)
    sparse_vec = qmodels.SparseVector(indices=sparse_indices, values=sparse_values)
    results = client.query_points(
        collection_name=collection,
        prefetch=[
            qmodels.Prefetch(query=sparse_vec, using="sparse", limit=limit * 2, filter=flt),
            qmodels.Prefetch(query=dense_vector, using="dense", limit=limit * 2, filter=flt),
        ],
        query=qmodels.FusionQuery(fusion=qmodels.Fusion.RRF),
        limit=limit,
        with_payload=True,
    )
    out: list[dict[str, Any]] = []
    for r in results.points:
        payload = r.payload or {}
        content = str(payload.get("page_content", ""))
        meta = {k: v for k, v in payload.items() if k != "page_content"}
        out.append(
            {
                "content": content,
                "metadata": meta,
                "score": float(r.score or 0.0),
                "chunk_id": str(r.id),
            }
        )
    return out


def dense_search(
    client: QdrantClient,
    *,
    collection: str,
    workspace_id: UUID,
    dense_vector: list[float],
    limit: int = 8,
) -> list[dict[str, Any]]:
    flt = _workspace_filter(workspace_id)
    results = client.query_points(
        collection_name=collection,
        query=dense_vector,
        using="dense",
        query_filter=flt,
        limit=limit,
        with_payload=True,
    )
    out: list[dict[str, Any]] = []
    for r in results.points:
        payload = r.payload or {}
        content = str(payload.get("page_content", ""))
        meta = {k: v for k, v in payload.items() if k != "page_content"}
        out.append(
            {
                "content": content,
                "metadata": meta,
                "score": float(r.score or 0.0),
                "chunk_id": str(r.id),
            }
        )
    return out


def upsert_knowledge_chunk(
    client: QdrantClient,
    *,
    collection: str,
    workspace_id: UUID,
    source_id: UUID,
    title: str,
    chunk_pk: int,
    content: str,
    dense_embedding: list[float],
    sparse_indices: list[int],
    sparse_values: list[float],
) -> None:
    setup_collection(client, collection)
    pid = qdrant_point_id(workspace_id, chunk_pk)
    point = qmodels.PointStruct(
        id=pid,
        vector={
            "dense": dense_embedding,
            "sparse": qmodels.SparseVector(indices=sparse_indices, values=sparse_values),
        },
        payload={
            "page_content": content,
            "workspace_id": str(workspace_id),
            "source_id": str(source_id),
            "chunk_pk": chunk_pk,
            "title": title,
            "doc_type": "knowledge",
            "source": str(source_id),
        },
    )
    client.upsert(collection_name=collection, points=[point])


async def upsert_knowledge_chunk_async(
    client: QdrantClient,
    **kwargs: Any,
) -> None:
    await asyncio.to_thread(upsert_knowledge_chunk, client, **kwargs)


async def hybrid_search_rrf_async(client: QdrantClient, **kwargs: Any) -> list[dict[str, Any]]:
    return await asyncio.to_thread(hybrid_search_rrf, client, **kwargs)


async def dense_search_async(client: QdrantClient, **kwargs: Any) -> list[dict[str, Any]]:
    return await asyncio.to_thread(dense_search, client, **kwargs)
