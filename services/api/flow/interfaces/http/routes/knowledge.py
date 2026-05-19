from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import urlparse
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile, status

from flow.application.knowledge_service import ingest_document
from flow.config import Settings, get_settings
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo
from flow.interfaces.http.schemas import KnowledgeCreateIn

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

MAX_UPLOAD_BYTES = 20_000_000  # 20 MB
ALLOWED_SUFFIXES = (".txt", ".md", ".mdx", ".csv", ".pdf", ".docx")


async def _assert_workspace(user_id: UUID, workspace_id: UUID, repo: FlowRepository) -> None:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if workspace_id not in allowed:
        raise HTTPException(status_code=403, detail="workspace not allowed")


def _extract_text(raw: bytes, filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        from flow.infrastructure.ingestion.extractors import extract_pdf
        return extract_pdf(raw)
    if lower.endswith(".docx"):
        from flow.infrastructure.ingestion.extractors import extract_docx
        return extract_docx(raw)
    return raw.decode("utf-8", errors="replace")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_knowledge(
    body: KnowledgeCreateIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    await _assert_workspace(user_id, body.workspace_id, repo)
    if not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY required for embeddings")
    sid = await ingest_document(
        repo=repo,
        openai_api_key=settings.openai_api_key,
        workspace_id=body.workspace_id,
        title=body.title,
        body=body.body,
        settings=settings,
    )
    return {"id": str(sid)}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_knowledge_file(
    workspace_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    await _assert_workspace(user_id, workspace_id, repo)
    if not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY required for embeddings")
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file too large (max 20MB)")
    name = (file.filename or "upload").strip()
    if not any(name.lower().endswith(s) for s in ALLOWED_SUFFIXES):
        raise HTTPException(
            status_code=400,
            detail=f"allowed types: {', '.join(ALLOWED_SUFFIXES)}",
        )
    try:
        text = await asyncio.to_thread(_extract_text, raw, name)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"could not extract text: {exc}") from exc
    if not text.strip():
        raise HTTPException(status_code=422, detail="could not extract text from file")
    title = Path(name).stem or "upload"
    sid = await ingest_document(
        repo=repo,
        openai_api_key=settings.openai_api_key,
        workspace_id=workspace_id,
        title=title,
        body=text,
        settings=settings,
    )
    return {"id": str(sid), "title": title}


@router.post("/crawl", status_code=status.HTTP_201_CREATED)
async def crawl_url(
    workspace_id: Annotated[UUID, Body()],
    url: Annotated[str, Body()],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    await _assert_workspace(user_id, workspace_id, repo)
    if not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY required for embeddings")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must start with http:// or https://")
    from flow.infrastructure.ingestion.extractors import extract_url_content
    try:
        text = await asyncio.to_thread(extract_url_content, url)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"could not fetch url: {exc}") from exc
    if not text.strip():
        raise HTTPException(status_code=422, detail="no extractable text found at url")
    title = urlparse(url).netloc or url[:60]
    sid = await ingest_document(
        repo=repo,
        openai_api_key=settings.openai_api_key,
        workspace_id=workspace_id,
        title=title,
        body=text,
        settings=settings,
    )
    return {"id": str(sid), "title": title}


@router.get("/{source_id}/chunks")
async def list_chunks(
    source_id: UUID,
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await _assert_workspace(user_id, workspace_id, repo)
    rows = await repo.list_chunks_for_source(source_id, workspace_id)
    return {
        "chunks": [
            {"id": str(r["id"]), "index": r["chunk_index"], "content": r["content"]}
            for r in rows
        ]
    }


@router.get("")
async def list_knowledge(
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await _assert_workspace(user_id, workspace_id, repo)
    rows = await repo.list_knowledge_sources(workspace_id)
    return {
        "sources": [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "created_at": r["created_at"].isoformat(),
                "chunk_count": int(r["chunk_count"] or 0),
                "ingest_status": r["ingest_status"] if "ingest_status" in r else "indexed",
                **(
                    {"ingest_error": r["ingest_error"]}
                    if "ingest_error" in r and r["ingest_error"]
                    else {}
                ),
            }
            for r in rows
        ]
    }


@router.delete("/{source_id}", status_code=204)
async def delete_knowledge_source(
    source_id: UUID,
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> None:
    await _assert_workspace(user_id, workspace_id, repo)
    deleted = await repo._pool.execute(
        "DELETE FROM knowledge_sources WHERE id = $1 AND workspace_id = $2",
        source_id, workspace_id,
    )
    if deleted == "DELETE 0":
        raise HTTPException(status_code=404, detail="source not found")
