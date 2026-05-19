"""Agent version management: snapshot, list, restore, compare."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from flow.application.genome_service import snapshot_genome
from flow.domain.genome import VersionStatus, VersionTrigger
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo
from flow.interfaces.http.schemas import SnapshotCreateIn

router = APIRouter(prefix="/api/v1/agents/{agent_id}/versions", tags=["agent-versions"])


@router.post("")
async def create_version(
    agent_id: UUID,
    body: SnapshotCreateIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Snapshot the current agent config as a named version."""
    agent = await _get_agent(repo, agent_id, user_id)
    workspace_id = agent["workspace_id"]

    try:
        version_id = await snapshot_genome(
            pool=repo._pool,
            agent_id=agent_id,
            workspace_id=workspace_id,
            trigger=VersionTrigger.MANUAL,
            version_label=body.version_label.strip(),
            created_by=user_id,
            status=VersionStatus.ACTIVE,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create version snapshot") from e
    return {"id": str(version_id), "version_label": body.version_label.strip()}


@router.get("")
async def list_versions(
    agent_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """List all config snapshots for an agent."""
    await _get_agent(repo, agent_id, user_id)  # authz check

    rows = await repo._pool.fetch(
        """
        SELECT id, version_label, config_snapshot, template, created_at, created_by, prompt_hash
        FROM agent_versions
        WHERE agent_id = $1
        ORDER BY created_at DESC
        """,
        agent_id,
    )
    versions = [
        {
            "id": str(r["id"]),
            "version_label": r["version_label"],
            "config_snapshot": r["config_snapshot"],
            "template": r["template"],
            "created_at": r["created_at"].isoformat(),
            "created_by": str(r["created_by"]) if r["created_by"] else None,
            "prompt_hash": r["prompt_hash"],
        }
        for r in rows
    ]
    return {"versions": versions}


@router.post("/{version_id}/restore")
async def restore_version(
    agent_id: UUID,
    version_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Restore an agent to a previous config version.

    The current config is auto-saved as a new version before restoring,
    so the operation is non-destructive.
    """
    agent = await _get_agent(repo, agent_id, user_id)
    workspace_id = agent["workspace_id"]

    # Get target version
    target = await repo._pool.fetchrow(
        "SELECT config_snapshot, template, version_label FROM agent_versions WHERE id = $1 AND agent_id = $2",
        version_id,
        agent_id,
    )
    if not target:
        raise HTTPException(status_code=404, detail="version not found")

    # Auto-save current config before restoring
    await snapshot_genome(
        pool=repo._pool,
        agent_id=agent_id,
        workspace_id=workspace_id,
        trigger=VersionTrigger.MANUAL,
        version_label=f"auto-save before restore to {target['version_label']}",
        created_by=user_id,
        status=VersionStatus.ACTIVE,
    )

    # Restore
    target_config = dict(target["config_snapshot"]) if isinstance(target["config_snapshot"], dict) else {}
    await repo.update_agent_config(agent_id, workspace_id, target_config)

    return {
        "restored_from": target["version_label"],
        "auto_saved": True,
        "config": target_config,
    }


@router.get("/{v1_id}/diff/{v2_id}")
async def diff_versions(
    agent_id: UUID,
    v1_id: UUID,
    v2_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Compare two versions and return their configs + diff summary."""
    await _get_agent(repo, agent_id, user_id)

    v1 = await repo._pool.fetchrow(
        "SELECT version_label, config_snapshot, template, created_at FROM agent_versions WHERE id=$1 AND agent_id=$2",
        v1_id,
        agent_id,
    )
    v2 = await repo._pool.fetchrow(
        "SELECT version_label, config_snapshot, template, created_at FROM agent_versions WHERE id=$1 AND agent_id=$2",
        v2_id,
        agent_id,
    )
    if not v1 or not v2:
        raise HTTPException(status_code=404, detail="version not found")

    c1 = dict(v1["config_snapshot"]) if isinstance(v1["config_snapshot"], dict) else {}
    c2 = dict(v2["config_snapshot"]) if isinstance(v2["config_snapshot"], dict) else {}

    # Compute config diff
    changes = []
    all_keys = set(list(c1.keys()) + list(c2.keys()))
    for key in sorted(all_keys):
        val1 = c1.get(key)
        val2 = c2.get(key)
        if val1 != val2:
            changes.append({"key": key, "old": val1, "new": val2})

    return {
        "v1": {
            "id": str(v1_id),
            "label": v1["version_label"],
            "config": c1,
            "template": v1["template"],
            "created_at": v1["created_at"].isoformat(),
        },
        "v2": {
            "id": str(v2_id),
            "label": v2["version_label"],
            "config": c2,
            "template": v2["template"],
            "created_at": v2["created_at"].isoformat(),
        },
        "changes": changes,
    }


# ── helpers ──


async def _get_agent(repo: FlowRepository, agent_id: UUID, user_id: UUID):
    ws_rows = await repo.list_workspaces_for_user(user_id)
    for r in ws_rows:
        agent = await repo.get_agent(agent_id, r["id"])
        if agent:
            return agent
    raise HTTPException(status_code=404, detail="agent not found")
