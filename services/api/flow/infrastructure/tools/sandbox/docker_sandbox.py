from __future__ import annotations

import asyncio
import os
import tempfile

from .base import SandboxResult


class DockerSandbox:
    async def run(self, code: str, timeout: int = 30) -> SandboxResult:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            tmp_path = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "run",
                "--rm",
                "--network=none",
                "--memory=128m",
                "--cpus=0.5",
                "-v",
                f"{tmp_path}:/code.py:ro",
                "python:3.12-slim",
                "python",
                "/code.py",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except TimeoutError:
                proc.kill()
                return SandboxResult(stdout="", stderr="Timeout", exit_code=124)
            return SandboxResult(
                stdout=stdout_b.decode(errors="replace"),
                stderr=stderr_b.decode(errors="replace"),
                exit_code=proc.returncode or 0,
            )
        finally:
            os.unlink(tmp_path)
