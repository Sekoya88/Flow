from __future__ import annotations

from .base import SandboxResult


class E2BSandbox:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def run(self, code: str, timeout: int = 30) -> SandboxResult:
        import asyncio

        from e2b_code_interpreter import AsyncSandbox

        sbx = await AsyncSandbox.create(api_key=self._api_key, timeout=timeout + 5)
        try:
            result = await asyncio.wait_for(
                sbx.run_code(code),
                timeout=timeout,
            )
            stdout = "\n".join(str(o) for o in (result.logs.stdout or []))
            stderr = "\n".join(str(o) for o in (result.logs.stderr or []))
            return SandboxResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=0 if not result.error else 1,
            )
        finally:
            await sbx.kill()
