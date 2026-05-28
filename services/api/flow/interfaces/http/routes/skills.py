from __future__ import annotations

import asyncio
import json
import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from flow.application.skill_parser import parse_skill_md
from flow.application.skill_playground import run_skill_test
from flow.config import Settings
from flow.infrastructure.persistence.repo import FlowRepository
from flow.infrastructure.persistence.skill_templates import SKILL_TEMPLATES
from flow.interfaces.http.deps import get_current_user_id, get_repo, get_settings_dep
from flow.interfaces.http.rate_limit import skill_test_rate_limit
from flow.interfaces.http.schemas import (
    DeactivateOut,
    SkillActivateOut,
    SkillCatalogOut,
    SkillCreateIn,
    SkillCreateOut,
    SkillHistoryOut,
    SkillImproveOut,
    SkillListOut,
    SkillPatchIn,
    SkillTestIn,
    PatchOut,
    SkillUsageOut,
    SkillVibeCreateIn,
    SkillVibeModifyIn,
    TrainingConfigIn,
    TrainingEpochOut,
    TrainingEventOut,
    TrainingEventsOut,
    TrainingRunDetailOut,
    TrainingRunOut,
    TrainingRunsOut,
    TrainingStartOut,
)

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


@router.get("", response_model=SkillListOut)
async def list_skills(
    workspace_id: UUID,
    agent_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> SkillListOut:
    rows = await repo.list_active_skills(agent_id, workspace_id)
    skills = []
    for r in rows:
        parsed = parse_skill_md(r["content_md"])
        skills.append(
            {
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
            }
        )
    return {"skills": skills}


@router.post("", response_model=SkillCreateOut)
async def create_skill(
    body: SkillCreateIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> SkillCreateOut:
    parsed = parse_skill_md(body.content_md)
    sid = await repo.upsert_agent_skill(
        agent_id=body.agent_id,
        workspace_id=body.workspace_id,
        name=body.name,
        content_md=body.content_md,
        category=parsed.category,
    )
    return {"id": str(sid)}


@router.get("/history", response_model=SkillHistoryOut)
async def skill_history(
    agent_id: UUID,
    name: str,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> SkillHistoryOut:
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


# ── Skills Hub (static paths — must precede /{skill_id} catch-all) ──────────


def _catalog_row_to_out(row) -> dict:
    parsed = parse_skill_md(row["content_md"])
    return {
        "id": str(row["id"]),
        "agent_id": str(row["agent_id"]),
        "agent_name": row["agent_name"],
        "name": parsed.name if parsed.name != "unnamed" else row["name"],
        "version": row["version"],
        "description": parsed.description or (row["description"] or ""),
        "category": parsed.category if parsed.category != "General" else (row.get("category") or "General"),
        "triggers": parsed.triggers or list(row["triggers"] or []),
        "allowed_tools": parsed.allowed_tools or list(row["allowed_tools"] or []),
        "metadata": parsed.metadata,
        "score": float(row["score"] or 0.0),
        "use_count": int(row["use_count"] or 0),
        "created_at": row["created_at"].isoformat(),
    }


@router.get("/catalog", response_model=SkillCatalogOut)
async def list_skills_catalog(
    workspace_id: Annotated[UUID, Query()],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    agent_id: Annotated[UUID | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    category: Annotated[str | None, Query(max_length=100)] = None,
) -> SkillCatalogOut:
    """Cross-agent catalog of active skills for the Skills Hub."""
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if workspace_id not in allowed:
        raise HTTPException(status_code=403, detail="workspace access denied")
    rows = await repo.list_skills_catalog(workspace_id, agent_id, q, category)
    return {"skills": [_catalog_row_to_out(r) for r in rows]}


@router.get("/templates")
async def list_skill_templates(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> dict:
    """Return the static skill template library."""
    return {
        "templates": [
            {
                "name": t["name"],
                "category": t["category"],
                "description": t["description"],
                "content_md": t["content_md"],
            }
            for t in SKILL_TEMPLATES
        ]
    }


@router.get("/training-runs")
async def list_workspace_training_runs(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """List recent training runs across all skills in the workspace."""
    ws_rows = await repo.list_workspaces_for_user(user_id)
    if not ws_rows:
        return {"runs": []}
    ws_id = ws_rows[0]["id"]
    rows = await repo._pool.fetch(
        """
        SELECT
            str.id, str.status, str.epoch, str.baseline_score, str.best_score,
            str.accepted, str.created_at, str.completed_at,
            s.id AS skill_id, s.name AS skill_name,
            a.id AS agent_id, a.name AS agent_name
        FROM skill_training_runs str
        JOIN agent_skills s ON s.id = str.skill_id
        JOIN agents a ON a.id = s.agent_id
        WHERE a.workspace_id = $1
        ORDER BY str.created_at DESC
        LIMIT $2
        """,
        ws_id,
        limit,
    )
    return {
        "runs": [
            {
                "id": str(r["id"]),
                "status": r["status"],
                "epoch": r["epoch"],
                "baseline_score": float(r["baseline_score"]) if r["baseline_score"] is not None else None,
                "best_score": float(r["best_score"]) if r["best_score"] is not None else None,
                "accepted": r["accepted"],
                "created_at": r["created_at"].isoformat(),
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
                "skill_id": str(r["skill_id"]),
                "skill_name": r["skill_name"],
                "agent_id": str(r["agent_id"]),
                "agent_name": r["agent_name"],
            }
            for r in rows
        ]
    }


# ── Gist preview (must be before /{skill_id} catch-all) ──────────────────────

@router.get("/preview-gist")
async def preview_gist(
    url: str,
    _user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> dict:
    """Server-side proxy for GitHub Gist preview (avoids browser rate-limits)."""
    import re
    import httpx

    match = re.search(r"([0-9a-f]{20,})", url)
    if not match:
        raise HTTPException(status_code=422, detail="could not extract gist ID")
    gist_id = match.group(1)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.github.com/gists/{gist_id}",
                headers={"Accept": "application/vnd.github.v3+json"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"gist fetch failed: {exc}") from exc

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="gist not found or not public")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"github API error {resp.status_code}")

    data = resp.json()
    files = data.get("files", {})
    md_files = [v for v in files.values() if v["filename"].endswith(".md")]
    file_entry = (md_files or list(files.values()) or [None])[0]
    if not file_entry:
        raise HTTPException(status_code=422, detail="gist has no files")

    content = file_entry.get("content") or ""
    name_match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
    name = name_match.group(1).strip() if name_match else file_entry["filename"].replace(".md", "")

    return {
        "gist_id": gist_id,
        "source_file": file_entry["filename"],
        "name": name,
        "preview": content[:1200],
    }


# ── GitHub repo preview (must be before /{skill_id} catch-all) ───────────────

class RepoSkillFile(BaseModel):
    path: str
    name: str
    sha: str
    size: int


class RepoPreviewOut(BaseModel):
    repo: str
    skills: list[RepoSkillFile]
    total: int
    truncated: bool


def _parse_repo_url(url: str) -> tuple[str, str]:
    """Accept 'owner/repo' or full github.com URL; return (owner, repo)."""
    import re
    url = url.strip().rstrip("/")
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", url)
    if m:
        return m.group(1), m.group(2)
    # bare owner/repo
    parts = url.split("/")
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0], parts[1]
    raise ValueError(f"could not parse GitHub repo URL: {url!r}")


@router.get("/preview-repo", response_model=RepoPreviewOut)
async def preview_repo(
    url: str,
    _user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> RepoPreviewOut:
    """List all .md files in a public GitHub repo (one API call via git/trees)."""
    import httpx

    try:
        owner, repo_name = _parse_repo_url(url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo_name}/git/trees/HEAD?recursive=1",
                headers={"Accept": "application/vnd.github+json"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"GitHub fetch failed: {exc}") from exc

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="repository not found or not public")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"GitHub API error {resp.status_code}")

    from pathlib import Path as _Path

    payload = resp.json()
    tree = payload.get("tree", [])
    skills = [
        RepoSkillFile(
            path=item["path"],
            name=_Path(item["path"]).stem,
            sha=item.get("sha", ""),
            size=item.get("size", 0),
        )
        for item in tree
        if item.get("type") == "blob" and item["path"].endswith(".md")
    ]
    return RepoPreviewOut(
        repo=f"{owner}/{repo_name}",
        skills=skills,
        total=len(skills),
        truncated=payload.get("truncated", False),
    )


@router.get("/{skill_id}")
async def get_skill(
    skill_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    skill = await repo.get_skill_by_id(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")
    ws_rows = await repo.list_workspaces_for_user(user_id)
    if skill["workspace_id"] not in {r["id"] for r in ws_rows}:
        raise HTTPException(status_code=403, detail="workspace access denied")
    parsed = parse_skill_md(skill["content_md"])
    return {
        "id": str(skill["id"]),
        "agent_id": str(skill["agent_id"]),
        "workspace_id": str(skill["workspace_id"]),
        "name": parsed.name if parsed.name != "unnamed" else skill["name"],
        "version": skill["version"],
        "description": parsed.description or "",
        "category": parsed.category or "General",
        "triggers": parsed.triggers,
        "allowed_tools": parsed.allowed_tools,
        "metadata": parsed.metadata,
        "content_md": skill["content_md"],
        "active": skill["active"],
        "score": float(skill.get("score", 1.0)),
        "use_count": int(skill.get("use_count", 0)),
        "created_at": skill["created_at"].isoformat(),
    }


@router.delete("/{skill_id}", response_model=DeactivateOut)
async def deactivate_skill(
    skill_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> DeactivateOut:
    await repo._pool.execute("UPDATE agent_skills SET active = false WHERE id = $1", skill_id)
    return {"deactivated": True}


@router.patch("/{skill_id}", response_model=dict)
async def patch_skill(
    skill_id: UUID,
    body: SkillPatchIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Update training_mode (and potentially other patchable fields) on a skill."""
    if body.training_mode is not None or "training_mode" in body.model_fields_set:
        found = await repo.patch_skill_training_mode(skill_id, body.training_mode)
        if not found:
            raise HTTPException(status_code=404, detail="Skill not found")
    return {"skill_id": str(skill_id), "training_mode": body.training_mode}


@router.post("/{skill_id}/activate", response_model=SkillActivateOut)
async def activate_skill_version(
    skill_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> SkillActivateOut:
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
    _rate: Annotated[None, Depends(skill_test_rate_limit)],
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


@router.post("/{skill_id}/improve", response_model=SkillImproveOut)
async def improve_skill(
    skill_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> SkillImproveOut:
    """Run the skill rewriter: fetch linked golden items, rewrite the skill body,
    create an inactive candidate version, and post a proposal for human review."""
    from flow.application.prompt_rewriter import FailedItem
    from flow.application.skill_rewriter import SkillRewriteResult, rewrite_skill

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
    proposal_body = json.dumps(
        {
            "skill_candidate_id": str(candidate_id),
            "failure_analysis": result.failure_analysis,
            "changelog": result.changelog,
            "confidence": result.confidence,
            "num_failures": len(failed_items),
        }
    )
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


@router.get("/{skill_id}/usage", response_model=SkillUsageOut)
async def skill_usage(
    skill_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    window: Annotated[int, Query(ge=1, le=90)] = 7,
) -> SkillUsageOut:
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


# ── Vibe (LLM-generated skills) ───────────────────────────────────────────────

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post("/vibe-create")
async def vibe_create_skill(
    body: SkillVibeCreateIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> StreamingResponse:
    """Stream a generated SKILL.md from a natural-language prompt.

    SSE events:
    - {"token": "..."} — incremental content
    - {"done": true, "skill_id": "..."} — final event with saved candidate id
    """
    ws_rows = await repo.list_workspaces_for_user(user_id)
    allowed = {r["id"] for r in ws_rows}
    if body.workspace_id not in allowed:
        raise HTTPException(status_code=403, detail="workspace access denied")

    from flow.application.skill_vibe import vibe_create_skill as _vibe_create

    async def event_generator():
        buffer: list[str] = []
        async for token in _vibe_create(settings, body.prompt, body.category):
            buffer.append(token)
            yield f"data: {json.dumps({'token': token})}\n\n"

        content_md = "".join(buffer).strip()
        parsed = parse_skill_md(content_md)
        skill_name = parsed.name if parsed.name != "unnamed" else "vibe-skill"
        skill_id = await repo.upsert_agent_skill(
            agent_id=body.agent_id,
            workspace_id=body.workspace_id,
            name=skill_name,
            content_md=content_md,
            category=parsed.category or body.category,
            initial_active=False,
        )
        yield f"data: {json.dumps({'done': True, 'skill_id': str(skill_id), 'name': skill_name})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/{skill_id}/vibe-modify")
async def vibe_modify_skill(
    skill_id: UUID,
    body: SkillVibeModifyIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> StreamingResponse:
    """Stream a modified SKILL.md from an existing skill and a change prompt.

    SSE events:
    - {"token": "..."} — incremental content
    - {"done": true, "skill_id": "...", "original_skill_id": "..."} — saved candidate id
    """
    skill = await repo.get_skill_by_id(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")

    ws_rows = await repo.list_workspaces_for_user(user_id)
    if skill["workspace_id"] not in {r["id"] for r in ws_rows}:
        raise HTTPException(status_code=403, detail="workspace access denied")

    from flow.application.skill_vibe import vibe_modify_skill as _vibe_modify

    async def event_generator():
        buffer: list[str] = []
        async for token in _vibe_modify(settings, skill["content_md"], body.prompt):
            buffer.append(token)
            yield f"data: {json.dumps({'token': token})}\n\n"

        content_md = "".join(buffer).strip()
        parsed = parse_skill_md(content_md)
        new_id = await repo.upsert_agent_skill(
            agent_id=skill["agent_id"],
            workspace_id=skill["workspace_id"],
            name=skill["name"],
            content_md=content_md,
            category=parsed.category or skill.get("category", "General"),
            initial_active=False,
        )
        yield f"data: {json.dumps({'done': True, 'skill_id': str(new_id), 'original_skill_id': str(skill_id)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=_SSE_HEADERS)



# ── Gist import ──────────────────────────────────────────────────────────────

class GistImportIn(BaseModel):
    gist_url: str  # e.g. "https://gist.github.com/user/abc123" or just "abc123"
    agent_id: UUID | None = None
    workspace_id: UUID


@router.post("/import/gist", status_code=status.HTTP_201_CREATED)
async def import_skill_from_gist(
    body: GistImportIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Fetch a public GitHub Gist and install its first .md file as a skill."""
    import re
    import httpx

    ws_rows = await repo.list_workspaces_for_user(user_id)
    if body.workspace_id not in {r["id"] for r in ws_rows}:
        raise HTTPException(status_code=403, detail="workspace access denied")

    # Accept full URL or bare gist ID
    gist_id_match = re.search(r"([0-9a-f]{20,})", body.gist_url)
    if not gist_id_match:
        raise HTTPException(status_code=422, detail="could not extract gist ID from URL")
    gist_id = gist_id_match.group(1)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://api.github.com/gists/{gist_id}",
                headers={"Accept": "application/vnd.github.v3+json"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"gist fetch failed: {exc}") from exc

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="gist not found or not public")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"github API error {resp.status_code}")

    data = resp.json()
    files = data.get("files", {})

    # Prefer .md files; fall back to .txt or first file
    md_files = [v for v in files.values() if v["filename"].endswith(".md")]
    txt_files = [v for v in files.values() if v["filename"].endswith(".txt")]
    file_entry = (md_files or txt_files or list(files.values()) or [None])[0]
    if not file_entry:
        raise HTTPException(status_code=422, detail="gist contains no files")

    content_md = file_entry.get("content") or ""
    if not content_md.strip():
        raise HTTPException(status_code=422, detail="gist file is empty")

    parsed = parse_skill_md(content_md)
    skill_name = parsed.name if parsed.name != "unnamed" else file_entry["filename"].replace(".md", "")

    effective_agent_id = body.agent_id
    if effective_agent_id is None:
        first_agent = await repo._pool.fetchrow(
            "SELECT id FROM agents WHERE workspace_id = $1 ORDER BY created_at LIMIT 1",
            body.workspace_id,
        )
        if not first_agent:
            raise HTTPException(status_code=422, detail="no agents in workspace")
        effective_agent_id = first_agent["id"]

    skill_id = await repo.upsert_agent_skill(
        agent_id=effective_agent_id,
        workspace_id=body.workspace_id,
        name=skill_name,
        content_md=content_md,
        category=parsed.category or "General",
        initial_active=True,
    )

    return {
        "skill_id": str(skill_id),
        "name": skill_name,
        "gist_id": gist_id,
        "source_file": file_entry["filename"],
    }


# ── Obsidian Skills import ───────────────────────────────────────────────────

_OBSIDIAN_SKILLS_TREE_URL = (
    "https://api.github.com/repos/kepano/obsidian-skills/git/trees/main?recursive=1"
)
_OBSIDIAN_RAW_BASE = "https://raw.githubusercontent.com/kepano/obsidian-skills/main/"


class ObsidianSkillsImportIn(BaseModel):
    agent_id: UUID
    workspace_id: UUID
    skills: list[str] | None = None  # None = import all; list of names to filter


@router.post("/import/obsidian-skills", status_code=status.HTTP_201_CREATED)
async def import_obsidian_skills(
    body: ObsidianSkillsImportIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Fetch skills from kepano/obsidian-skills on GitHub and install them as Flow skills."""
    import httpx

    ws_rows = await repo.list_workspaces_for_user(user_id)
    if body.workspace_id not in {r["id"] for r in ws_rows}:
        raise HTTPException(status_code=403, detail="workspace access denied")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            tree_resp = await client.get(
                _OBSIDIAN_SKILLS_TREE_URL,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"GitHub fetch failed: {exc}") from exc

    if tree_resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"GitHub API error {tree_resp.status_code}")

    skill_paths = [
        item["path"]
        for item in tree_resp.json().get("tree", [])
        if item["path"].endswith("SKILL.md")
    ]

    if body.skills:
        skill_paths = [p for p in skill_paths if any(s in p for s in body.skills)]

    imported: list[dict] = []
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=30) as client:
        for path in skill_paths:
            try:
                r = await client.get(_OBSIDIAN_RAW_BASE + path)
                if r.status_code != 200:
                    errors.append(f"{path}: HTTP {r.status_code}")
                    continue
                content_md = r.text
                parsed = parse_skill_md(content_md)
                name = parsed.name if parsed.name != "unnamed" else path.split("/")[0]
                skill_id = await repo.upsert_agent_skill(
                    agent_id=body.agent_id,
                    workspace_id=body.workspace_id,
                    name=name,
                    content_md=content_md,
                    category=parsed.category or "Obsidian",
                    initial_active=True,
                )
                imported.append({"id": str(skill_id), "name": name})
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{path}: {exc}")

    return {"imported_count": len(imported), "skills": imported, "errors": errors}


# ── GitHub repo import ────────────────────────────────────────────────────────

class RepoImportIn(BaseModel):
    repo_url: str
    workspace_id: UUID
    paths: list[str] | None = None  # None = import all .md files
    agent_id: UUID | None = None  # None = first agent in workspace


class RepoImportOut(BaseModel):
    imported: int
    skills: list[dict]
    errors: list[str]


@router.post("/import/repo", response_model=RepoImportOut, status_code=status.HTTP_201_CREATED)
async def import_skills_from_repo(
    body: RepoImportIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> RepoImportOut:
    """Fetch .md skill files from a public GitHub repo and install them as Flow skills."""
    import httpx
    from pathlib import Path as _Path

    ws_rows = await repo.list_workspaces_for_user(user_id)
    if body.workspace_id not in {r["id"] for r in ws_rows}:
        raise HTTPException(status_code=403, detail="workspace access denied")

    try:
        owner, repo_name = _parse_repo_url(body.repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Resolve effective agent (fall back to first in workspace when not provided)
    effective_agent_id = body.agent_id
    if effective_agent_id is None:
        first_agent = await repo._pool.fetchrow(
            "SELECT id FROM agents WHERE workspace_id = $1 ORDER BY created_at LIMIT 1",
            body.workspace_id,
        )
        if not first_agent:
            raise HTTPException(status_code=422, detail="no agents in workspace")
        effective_agent_id = first_agent["id"]

    # If no explicit path list, preview the repo to get all .md paths
    paths_to_import: list[str] = body.paths or []
    if not paths_to_import:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                tree_resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo_name}/git/trees/HEAD?recursive=1",
                    headers={"Accept": "application/vnd.github+json"},
                )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"GitHub fetch failed: {exc}") from exc
        if tree_resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"GitHub API error {tree_resp.status_code}")
        paths_to_import = [
            item["path"]
            for item in tree_resp.json().get("tree", [])
            if item.get("type") == "blob" and item["path"].endswith(".md")
        ]

    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo_name}/HEAD/"
    imported_skills: list[dict] = []
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=30) as client:
        for path in paths_to_import:
            try:
                r = await client.get(raw_base + path)
                if r.status_code != 200:
                    errors.append(f"{path}: HTTP {r.status_code}")
                    continue
                content_md = r.text
                if not content_md.strip():
                    errors.append(f"{path}: empty file")
                    continue
                parsed = parse_skill_md(content_md)
                skill_name = (
                    parsed.name if parsed.name != "unnamed" else _Path(path).stem
                )
                skill_id = await repo.upsert_agent_skill(
                    agent_id=effective_agent_id,
                    workspace_id=body.workspace_id,
                    name=skill_name,
                    content_md=content_md,
                    category=parsed.category or "GitHub",
                    initial_active=True,
                )
                imported_skills.append({"id": str(skill_id), "name": skill_name, "path": path})
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{path}: {exc}")

    return RepoImportOut(imported=len(imported_skills), skills=imported_skills, errors=errors)


# ── Skill training ────────────────────────────────────────────────────────────


@router.post("/{skill_id}/train", response_model=TrainingStartOut)
async def start_skill_training(
    skill_id: UUID,
    body: TrainingConfigIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> TrainingStartOut:
    """Create a training run and enqueue the ARQ job."""
    run_id = await repo.create_training_run(
        skill_id=skill_id,
        agent_id=body.agent_id,
        workspace_id=body.workspace_id,
        edit_budget=body.edit_budget,
    )
    from flow.infrastructure.queue.client import get_arq_pool

    arq_pool = await get_arq_pool()
    await arq_pool.enqueue_job(
        "run_skill_training",
        str(run_id),
        str(skill_id),
        str(body.agent_id),
        str(body.workspace_id),
        {
            "edit_budget": body.edit_budget,
            "max_epochs": body.max_epochs,
            "min_val_improvement": body.min_val_improvement,
        },
    )
    return TrainingStartOut(run_id=str(run_id), skill_id=str(skill_id), status="pending")


@router.get("/{skill_id}/training-runs", response_model=TrainingRunsOut)
async def list_skill_training_runs(
    skill_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> TrainingRunsOut:
    rows = await repo.list_training_runs(skill_id)
    runs = [
        TrainingRunOut(
            id=str(r["id"]),
            status=r["status"],
            epoch=r["epoch"],
            baseline_score=r["baseline_score"],
            best_score=r["best_score"],
            accepted=r["accepted"],
            created_at=r["created_at"].isoformat(),
            error_message=r["error_message"],
        )
        for r in rows
    ]
    return TrainingRunsOut(runs=runs)


@router.get("/{skill_id}/training-runs/{run_id}", response_model=TrainingRunDetailOut)
async def get_skill_training_run(
    skill_id: UUID,
    run_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> TrainingRunDetailOut:
    import json as _json

    run = await repo.get_training_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Training run not found")

    epochs, raw_patches = await asyncio.gather(
        repo.list_training_epochs(run_id),
        repo.list_run_patches(run_id),
    )

    epoch_outs = [
        TrainingEpochOut(
            epoch=e["epoch"],
            eval_score=e["eval_score"],
            baseline_score=e["baseline_score"],
            accepted=e["accepted"],
            patch_count=e["patch_count"],
            created_at=e["created_at"].isoformat(),
        )
        for e in epochs
    ]

    patch_outs: list[PatchOut] = []
    patches_applied = 0
    patches_rejected = 0
    for p in raw_patches:
        pj = p["patch_json"]
        if isinstance(pj, str):
            try:
                pj = _json.loads(pj)
            except Exception:
                pj = {}
        patch_outs.append(PatchOut(
            op=str(pj.get("op", "")),
            target=str(pj.get("target", "")),
            content=str(pj.get("content", "")) if pj.get("content") else None,
            impact_score=float(pj["impact_score"]) if pj.get("impact_score") is not None else None,
            applied=bool(p["applied"]),
            rejected=bool(p["rejected"]),
        ))
        if p["applied"]:
            patches_applied += 1
        if p["rejected"]:
            patches_rejected += 1

    # Fetch original skill content
    original_content = await repo.get_skill_content(skill_id)

    # Fetch candidate skill content — accepted first, fall back to any epoch with a candidate
    candidate_content: str | None = None
    for ep in reversed(epochs):
        if ep["accepted"] and ep["candidate_skill_id"]:
            candidate_content = await repo.get_skill_content(ep["candidate_skill_id"])
            break
    if candidate_content is None:
        for ep in reversed(epochs):
            if ep["candidate_skill_id"]:
                candidate_content = await repo.get_skill_content(ep["candidate_skill_id"])
                break

    return TrainingRunDetailOut(
        id=str(run["id"]),
        status=run["status"],
        epoch=run["epoch"],
        baseline_score=run["baseline_score"],
        best_score=run["best_score"],
        accepted=run["accepted"],
        created_at=run["created_at"].isoformat(),
        epochs=epoch_outs,
        patches_applied=patches_applied,
        patches_rejected=patches_rejected,
        patches=patch_outs,
        original_content=original_content,
        candidate_content=candidate_content,
    )


@router.get("/{skill_id}/training-runs/{run_id}/events", response_model=TrainingEventsOut)
async def get_training_run_events(
    skill_id: UUID,
    run_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> TrainingEventsOut:
    """Return all COT events for a training run, ordered chronologically."""
    events = await repo.list_training_events(run_id)
    return TrainingEventsOut(
        events=[
            TrainingEventOut(
                id=str(e["id"]),
                stage=e["stage"],
                kind=e["kind"],
                message=e["message"],
                data=e["data"] if isinstance(e["data"], dict) else (json.loads(e["data"]) if e["data"] else None),
                created_at=e["created_at"].isoformat(),
            )
            for e in events
        ]
    )
