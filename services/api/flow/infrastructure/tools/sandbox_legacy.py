from __future__ import annotations

import asyncio


async def run_python_snippet(code: str, *, timeout_sec: float = 5.0) -> str:
    """Execute user skill code defining `run(input: str) -> str` (dev MVP)."""
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
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
    except TimeoutError:
        proc.kill()
        return "[sandbox] timeout"
    if proc.returncode != 0:
        return f"[sandbox rc={proc.returncode}] {stderr.decode()[:4000]}"
    return stdout.decode()[:8000] or "(empty)"
