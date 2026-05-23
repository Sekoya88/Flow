from __future__ import annotations

from pathlib import Path

import yaml


class LocalVaultService:
    def __init__(self, vault_path: str) -> None:
        self.vault = Path(vault_path).expanduser()
        self.vault.mkdir(parents=True, exist_ok=True)

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
        full = self.vault / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(self._render_note(content, frontmatter or {}), encoding="utf-8")
        return str(full)

    async def append_note(self, path: str, content: str) -> bool:
        full = self.vault / path
        if not full.exists():
            return False
        with full.open("a", encoding="utf-8") as f:
            f.write(f"\n{content}")
        return True

    async def read_note(self, path: str) -> str:
        full = self.vault / path
        if not full.exists():
            return ""
        return full.read_text(encoding="utf-8")

    async def list_notes(self, prefix: str = "") -> list[str]:
        base = self.vault / prefix if prefix else self.vault
        if not base.exists():
            return []
        return [str(p.relative_to(self.vault)) for p in base.rglob("*.md")]
