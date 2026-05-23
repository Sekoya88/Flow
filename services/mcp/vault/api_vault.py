from __future__ import annotations

from typing import Optional

import httpx
import yaml


class ObsidianAPIVaultService:
    """Vault backend using the Obsidian Local REST API plugin."""

    def __init__(self, api_url: str, api_key: Optional[str] = None) -> None:
        self.api_url = api_url.rstrip("/")
        self.headers: dict = {"Content-Type": "text/markdown"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    def _render_note(self, content: str, frontmatter: dict) -> str:
        if frontmatter:
            fm_str = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)
            return f"---\n{fm_str}---\n\n{content}"
        return content

    async def create_note(
        self,
        path: str,
        content: str,
        frontmatter: dict | None = None,
        workspace_id: str | None = None,
    ) -> str:
        body = self._render_note(content, frontmatter or {})
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.put(
                f"{self.api_url}/vault/{path}",
                content=body.encode("utf-8"),
                headers=self.headers,
            )
            r.raise_for_status()
        return f"obsidian://{path}"

    async def append_note(self, path: str, content: str) -> bool:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{self.api_url}/vault/{path}",
                content=f"\n{content}".encode("utf-8"),
                headers=self.headers,
            )
            return r.status_code < 400

    async def read_note(self, path: str) -> str:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{self.api_url}/vault/{path}",
                headers={"Accept": "text/markdown", **self.headers},
            )
            if r.status_code == 404:
                return ""
            r.raise_for_status()
            return r.text

    async def list_notes(self, prefix: str = "") -> list[str]:
        url = f"{self.api_url}/vault/" + (prefix if prefix else "")
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, headers=self.headers)
            r.raise_for_status()
            data = r.json()
            return [f["path"] for f in data.get("files", []) if f["path"].endswith(".md")]
