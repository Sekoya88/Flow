from __future__ import annotations

import json
import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from flow.application.skill_parser import parse_skill_md
from flow.application.skill_playground import run_skill_test
from flow.config import Settings
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo, get_settings_dep

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


class SkillCreateIn(BaseModel):
    workspace_id: UUID
    agent_id: UUID
    name: str = Field(min_length=1, max_length=200)
    content_md: str = Field(min_length=1, max_length=10000)


class SkillOut(BaseModel):
    id: str
    name: str
    version: int
    content_md: str
    description: str = ""
    allowed_tools: list[str] = []
    triggers: list[str] = []
    metadata: dict = {}
    active: bool = True
    score: float = 1.0
    use_count: int = 0
    created_at: str = ""


@router.get("")
async def list_skills(
    workspace_id: UUID,
    agent_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    rows = await repo.list_active_skills(agent_id, workspace_id)
    skills = []
    for r in rows:
        parsed = parse_skill_md(r["content_md"])
        skills.append({
            "id": str(r["id"]),
            "name": parsed.name if parsed.name != "unnamed" else r["name"],
            "version": r["version"],
            "content_md": r["content_md"],
            "description": parsed.description,
            "allowed_tools": parsed.allowed_tools,
            "triggers": parsed.triggers,
            "metadata": parsed.metadata,
            "active": True,
            "score": r.get("score", 1.0) if hasattr(r, "get") else 1.0,
            "use_count": r.get("use_count", 0) if hasattr(r, "get") else 0,
            "created_at": r["created_at"].isoformat(),
        })
    return {"skills": skills}


@router.post("")
async def create_skill(
    body: SkillCreateIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    sid = await repo.upsert_agent_skill(
        agent_id=body.agent_id,
        workspace_id=body.workspace_id,
        name=body.name,
        content_md=body.content_md,
    )
    return {"id": str(sid)}


@router.get("/history")
async def skill_history(
    agent_id: UUID,
    name: str,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    rows = await repo.get_skill_history(agent_id, name)
    return {
        "versions": [
            {
                "id": str(r["id"]),
                "version": r["version"],
                "content_md": r["content_md"],
                "active": r["active"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


@router.delete("/{skill_id}")
async def deactivate_skill(
    skill_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    await repo._pool.execute(
        "UPDATE agent_skills SET active = false WHERE id = $1", skill_id
    )
    return {"deactivated": True}


# ── Skills Hub ───────────────────────────────────────────────────────────────


class SkillTestIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


def _catalog_row_to_out(row) -> dict:
    parsed = parse_skill_md(row["content_md"])
    return {
        "id": str(row["id"]),
        "agent_id": str(row["agent_id"]),
        "agent_name": row["agent_name"],
        "name": parsed.name if parsed.name != "unnamed" else row["name"],
        "version": row["version"],
        "description": parsed.description or (row["description"] or ""),
        "triggers": parsed.triggers or list(row["triggers"] or []),
        "allowed_tools": parsed.allowed_tools or list(row["allowed_tools"] or []),
        "metadata": parsed.metadata or dict(row["metadata"] or {}),
        "score": float(row["score"] or 0.0),
        "use_count": int(row["use_count"] or 0),
        "created_at": row["created_at"].isoformat(),
    }


@router.get("/catalog")
async def list_skills_catalog(
    workspace_id: Annotated[UUID, Query()],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    agent_id: Annotated[UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> dict:
    """Cross-agent catalog of active skills for the Skills Hub."""
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if workspace_id not in allowed:
        raise HTTPException(status_code=403, detail="workspace access denied")
    rows = await repo.list_skills_catalog(workspace_id, agent_id, q)
    return {"skills": [_catalog_row_to_out(r) for r in rows]}


@router.post("/{skill_id}/activate")
async def activate_skill_version(
    skill_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Make this historical version the active one; deactivate siblings."""
    row = await repo.activate_skill_version(skill_id)
    if row is None:
        raise HTTPException(status_code=404, detail="skill not found")
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "version": row["version"],
        "active": row["active"],
    }


@router.post("/{skill_id}/test")
async def test_skill(
    skill_id: UUID,
    body: SkillTestIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> StreamingResponse:
    """Stream LLM tokens for a single-skill, single-prompt isolated run."""
    skill = await repo.get_skill_by_id(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")

    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if skill["workspace_id"] not in allowed:
        raise HTTPException(status_code=403, detail="workspace access denied")

    async def event_generator():
        async for token in run_skill_test(
            settings=settings,
            skill_content_md=skill["content_md"],
            prompt=body.prompt,
        ):
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Skill self-improvement loop ───────────────────────────────────────────────


@router.post("/{skill_id}/improve")
async def improve_skill(
    skill_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Run the skill rewriter: fetch linked golden items, rewrite the skill body,
    create an inactive candidate version, and post a proposal for human review."""
    from flow.application.skill_rewriter import rewrite_skill, SkillRewriteResult
    from flow.application.prompt_rewriter import FailedItem

    skill = await repo.get_skill_by_id(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")

    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if skill["workspace_id"] not in allowed:
        raise HTTPException(status_code=403, detail="workspace access denied")

    # Gather failed golden items linked to this skill
    linked = await repo.list_golden_items_for_skill(skill_id)
    if not linked:
        raise HTTPException(status_code=422, detail="no golden items linked to this skill — attach items first")

    # Pull recent golden_results for those items to find failures
    item_ids = [r["id"] for r in linked]
    results_rows = await repo._pool.fetch(
        """
        SELECT gr.item_id, gi.input_text, gi.expected_output,
               gr.actual_output, gr.score, gr.grading_rationale
        FROM golden_results gr
        JOIN golden_items gi ON gi.id = gr.item_id
        WHERE gr.item_id = ANY($1::uuid[])
          AND gr.score < 0.7
        ORDER BY gr.created_at DESC
        LIMIT 20
        """,
        item_ids,
    )
    if not results_rows:
        raise HTTPException(status_code=422, detail="no recent failures found — run an evaluation first")

    failed_items = [
        FailedItem(
            input_text=r["input_text"],
            expected_output=r["expected_output"],
            actual_output=r["actual_output"] or "",
            score=float(r["score"]),
            rationale=r["grading_rationale"] or "",
        )
        for r in results_rows
    ]

    openai_key = os.environ.get("FLOW_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    result: SkillRewriteResult = await rewrite_skill(
        current_content_md=skill["content_md"],
        failed_items=failed_items,
        openai_api_key=openai_key,
    )

    if result.confidence < 0.3:
        return {
            "improved": False,
            "reason": "low confidence rewrite",
            "confidence": result.confidence,
        }

    if result.improved_content_md.strip() == skill["content_md"].strip():
        return {"improved": False, "reason": "no change proposed", "confidence": result.confidence}

    # Create inactive candidate version
    candidate_id = await repo.upsert_agent_skill(
        agent_id=skill["agent_id"],
        workspace_id=skill["workspace_id"],
        name=skill["name"],
        content_md=result.improved_content_md,
        initial_active=False,
    )

    # Post proposal with embedded skill_candidate_id for approval routing
    changelog_md = "\n".join(f"- {c}" for c in result.changelog)
    proposal_body = json.dumps({
        "skill_candidate_id": str(candidate_id),
        "failure_analysis": result.failure_analysis,
        "changelog": result.changelog,
        "confidence": result.confidence,
        "num_failures": len(failed_items),
    })
    proposal_id = await repo.create_proposal(
        workspace_id=skill["workspace_id"],
        user_id=user_id,
        title=f"Skill improvement: {skill['name']}",
        body=proposal_body,
    )

    return {
        "improved": True,
        "candidate_skill_id": str(candidate_id),
        "proposal_id": str(proposal_id),
        "confidence": result.confidence,
        "changelog": result.changelog,
        "failure_analysis": result.failure_analysis,
    }


@router.get("/{skill_id}/usage")
async def skill_usage(
    skill_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    window: Annotated[int, Query(ge=1, le=90)] = 7,
) -> dict:
    """Return daily match counts for the last N days (for sparkline chart)."""
    skill = await repo.get_skill_by_id(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")

    ws_rows = await repo.list_workspaces_for_user(user_id)
    if skill["workspace_id"] not in {r["id"] for r in ws_rows}:
        raise HTTPException(status_code=403, detail="workspace access denied")

    rows = await repo.count_skill_events_by_day(skill_id, window_days=window)
    return {
        "skill_id": str(skill_id),
        "window_days": window,
        "data": [{"date": str(r["date"]), "count": r["count"]} for r in rows],
    }
