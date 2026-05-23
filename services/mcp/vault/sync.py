from __future__ import annotations

from .local_vault import LocalVaultService
from .cloud_vault import ObsidianCloudVaultService


async def sync_local_to_cloud(
    local: LocalVaultService,
    cloud: ObsidianCloudVaultService,
    workspace_id: str,
    prefix: str = "",
) -> dict:
    """Upload all local notes to cloud storage. Returns {synced, failed}."""
    notes = await local.list_notes(prefix)
    synced, failed = 0, 0
    for note_path in notes:
        try:
            content = await local.read_note(note_path)
            await cloud.create_note(note_path, content, workspace_id=workspace_id)
            synced += 1
        except Exception:
            failed += 1
    return {"synced": synced, "failed": failed, "total": len(notes)}
