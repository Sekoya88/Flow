from __future__ import annotations

import asyncio

from .base import SandboxResult


class UnsafeSandbox:
    async def run(self, code: str, timeout: int = 30) -> SandboxResult:
        loader = f"""
locals_dict = {{}}
exec({code!r}, locals_dict, locals_dict)
_run = locals_dict.get("run")
import sys
if callable(_run):
    sys.stdout.write(str(_run("")))
else:
    sys.stderr.write("Skill code must define run(input: str) -> str\\n")
"""
        proc = await asyncio.create_subprocess_exec(
            "python3",
            "-c",
            loader,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=float(timeout))
        except TimeoutError:
            proc.kill()
            return SandboxResult(stdout="", stderr="timeout", exit_code=124)
        return SandboxResult(
            stdout=stdout_b.decode()[:8000],
            stderr=stderr_b.decode()[:4000],
            exit_code=proc.returncode or 0,
        )
