from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from flow.application.knowledge_service import ingest_document
from flow.config import Settings, get_settings
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo
from flow.interfaces.http.schemas import KnowledgeCreateIn

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

MAX_UPLOAD_BYTES = 512_000
ALLOWED_SUFFIXES = (".txt", ".md", ".mdx", ".csv")


async def _assert_workspace(user_id: UUID, workspace_id: UUID, repo: FlowRepository) -> None:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if workspace_id not in allowed:
        raise HTTPException(status_code=403, detail="workspace not allowed")


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
        raise HTTPException(status_code=413, detail="file too large (max 512KB)")
    name = (file.filename or "upload").strip()
    lower = name.lower()
    if not any(lower.endswith(s) for s in ALLOWED_SUFFIXES):
        raise HTTPException(
            status_code=400,
            detail=f"allowed types: {', '.join(ALLOWED_SUFFIXES)}",
        )
    text = raw.decode("utf-8", errors="replace")
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
