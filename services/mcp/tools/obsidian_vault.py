from __future__ import annotations

from ..auth import get_current_context
from ..config import settings


def _get_vault_service():
    mode = settings.obsidian_mode
    if mode == "filesystem":
        from ..vault.local_vault import LocalVaultService
        return LocalVaultService(settings.obsidian_vault_path)
    if mode == "api":
        from ..vault.api_vault import ObsidianAPIVaultService
        return ObsidianAPIVaultService(settings.obsidian_api_url, settings.obsidian_api_key)
    if mode == "cloud":
        from ..vault.cloud_vault import ObsidianCloudVaultService
        return ObsidianCloudVaultService(settings.obsidian_bucket, settings.aws_endpoint_url)
    raise ValueError(f"Unknown vault mode: {mode}")


def register_obsidian_tools(mcp):  # type: ignore[no-untyped-def]

    @mcp.tool()
    async def obsidian_create_note(
        path: str,
        content: str,
        frontmatter: dict | None = None,
    ) -> str:
        """Create a Markdown note in the Obsidian vault.
        path = relative path e.g. 'Research/2026-05/paper.md'
        Returns the absolute path or URI of the created note."""
        ctx = get_current_context()
        vault = _get_vault_service()
        return await vault.create_note(
            path, content, frontmatter or {}, ctx.get("workspace_id")
        )

    @mcp.tool()
    async def obsidian_append_note(path: str, content: str) -> bool:
        """Append content to the end of an existing Obsidian note."""
        vault = _get_vault_service()
        return await vault.append_note(path, content)

    @mcp.tool()
    async def obsidian_read_note(path: str) -> str:
        """Read the content of an Obsidian note."""
        vault = _get_vault_service()
        return await vault.read_note(path)

    @mcp.tool()
    async def obsidian_list_notes(prefix: str = "") -> list[str]:
        """List notes in the vault, optionally filtered by path prefix."""
        vault = _get_vault_service()
        return await vault.list_notes(prefix)
