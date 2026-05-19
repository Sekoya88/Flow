from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import UploadFile

from flow.application.kg_parser import ObsidianDocument


async def parse_upload(files: list[UploadFile]) -> list[ObsidianDocument]:
    """Read multipart-uploaded .md files into ObsidianDocuments."""
    docs: list[ObsidianDocument] = []
    for f in files:
        if f.filename and not f.filename.endswith(".md"):
            continue
        raw = await f.read()
        docs.append(
            ObsidianDocument(
                filename=f.filename or "unknown.md",
                raw_content=raw.decode("utf-8", errors="replace"),
                source="upload",
            )
        )
    return docs


async def fetch_from_obsidian_api(
    base_url: str,
    api_key: str,
    vault_path: str = "/",
) -> list[ObsidianDocument]:
    """Fetch notes from Obsidian Local REST API plugin.

    Plugin: https://github.com/coddingtonbear/obsidian-local-rest-api
    Endpoints used:
      GET /vault/{path}/  -> list directory
      GET /vault/{path}   -> get file content
    """
    base = base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"}
    docs: list[ObsidianDocument] = []

    async with httpx.AsyncClient(timeout=30, verify=False) as client:  # noqa: S501 — local only
        # List all files under vault_path
        list_path = vault_path.rstrip("/") + "/"
        resp = await client.get(f"{base}/vault{list_path}", headers=headers)
        resp.raise_for_status()
        listing = resp.json()

        md_files: list[str] = []
        for item in listing.get("files", []):
            if isinstance(item, str) and item.endswith(".md"):
                md_files.append(item)
            elif isinstance(item, dict) and item.get("path", "").endswith(".md"):
                md_files.append(item["path"])

        # Fetch each file concurrently (max 10 at a time)
        sem = asyncio.Semaphore(10)

        async def fetch_one(filepath: str) -> ObsidianDocument | None:
            async with sem:
                try:
                    r = await client.get(f"{base}/vault/{filepath}", headers=headers)
                    r.raise_for_status()
                    return ObsidianDocument(
                        filename=filepath,
                        raw_content=r.text,
                        source="api",
                    )
                except Exception:
                    return None

        results = await asyncio.gather(*[fetch_one(f) for f in md_files])
        docs = [d for d in results if d is not None]

    return docs


async def sync_from_path(
    vault_path: str,
    since: datetime | None = None,
) -> list[ObsidianDocument]:
    """Walk local filesystem for .md files, optionally filtering by mtime."""
    root = Path(vault_path)
    if not root.exists():
        raise FileNotFoundError(f"Vault path not found: {vault_path}")

    docs: list[ObsidianDocument] = []
    for md_file in root.rglob("*.md"):
        if since is not None:
            mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
            if mtime <= since:
                continue
        relative = str(md_file.relative_to(root))
        raw = md_file.read_text(encoding="utf-8", errors="replace")
        docs.append(
            ObsidianDocument(
                filename=relative,
                raw_content=raw,
                source="sync",
            )
        )
    return docs
