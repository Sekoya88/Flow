from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int

    def __str__(self) -> str:
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"[stderr] {self.stderr}")
        if self.exit_code != 0:
            parts.append(f"[exit {self.exit_code}]")
        return "\n".join(parts) or "(no output)"


class Sandbox(Protocol):
    async def run(self, code: str, timeout: int = 30) -> SandboxResult: ...
