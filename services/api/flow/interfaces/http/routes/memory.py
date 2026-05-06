from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from flow.config import Settings, get_settings
from flow.infrastructure.llm import embeddings as emb_svc
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


class MemoryCreateIn(BaseModel):
    workspace_id: UUID
    agent_id: UUID
    content: str = Field(min_length=1, max_length=16000)


async def _assert_workspace(user_id: UUID, workspace_id: UUID, repo: FlowRepository) -> None:
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if workspace_id not in allowed:
        raise HTTPException(status_code=403, detail="workspace not allowed")


@router.post("")
async def create_memory(
    body: MemoryCreateIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    await _assert_workspace(user_id, body.workspace_id, repo)
    agent = await repo.get_agent(body.agent_id, body.workspace_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    emb = None
    if settings.openai_api_key:
        emb = (await emb_svc.embed_texts(api_key=settings.openai_api_key, texts=[body.content]))[0]
    mid = await repo.insert_memory(body.workspace_id, body.agent_id, user_id, body.content, emb)
    return {"id": str(mid)}


@router.get("/tiered")
async def get_tiered_memories(
    workspace_id: UUID,
    agent_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Return episodic + semantic memories for the MemoryDrawer."""
    await _assert_workspace(user_id, workspace_id, repo)
    agent = await repo.get_agent(agent_id, workspace_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")

    episodic_rows = await repo.list_episodic_memories(workspace_id, agent_id, user_id)
    semantic_rows = await repo.list_semantic_memories(workspace_id, agent_id, user_id)

    return {
        "episodic": [
            {
                "id": str(r["id"]),
                "content": r["content"],
                "execution_id": str(r["execution_id"]) if r["execution_id"] else None,
                "created_at": r["created_at"].isoformat(),
            }
            for r in episodic_rows
        ],
        "semantic": [
            {
                "id": str(r["id"]),
                "content": r["content"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in semantic_rows
        ],
    }


@router.delete("/episodic/{memory_id}")
async def delete_episodic_memory(
    memory_id: UUID,
    workspace_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await _assert_workspace(user_id, workspace_id, repo)
    deleted = await repo.delete_episodic_memory(memory_id, workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"deleted": True}
