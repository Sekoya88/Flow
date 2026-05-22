from __future__ import annotations

import asyncio

import httpx

from ..config import settings

_GH_HEADERS = {
    "Accept": "application/vnd.github.v3+json",
}


def _gh_headers() -> dict:
    if not settings.github_token:
        raise ValueError("GITHUB_TOKEN not configured")
    return {**_GH_HEADERS, "Authorization": f"token {settings.github_token}"}


def register_github_tools(mcp):  # type: ignore[no-untyped-def]

    @mcp.tool()
    async def github_trigger_workflow(
        repo: str,
        workflow_id: str,
        ref: str = "main",
        inputs: dict | None = None,
    ) -> str:
        """Trigger a GitHub Actions workflow. repo = 'owner/repo'.
        Returns run_id to track execution."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_id}/dispatches",
                json={"ref": ref, "inputs": inputs or {}},
                headers=_gh_headers(),
            )
            r.raise_for_status()
            await asyncio.sleep(2)
            runs = await client.get(
                f"https://api.github.com/repos/{repo}/actions/runs?per_page=1",
                headers=_gh_headers(),
            )
            runs.raise_for_status()
            return str(runs.json()["workflow_runs"][0]["id"])

    @mcp.tool()
    async def github_get_run_status(repo: str, run_id: str) -> dict:
        """Get the status of a GitHub Actions workflow run."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"https://api.github.com/repos/{repo}/actions/runs/{run_id}",
                headers=_gh_headers(),
            )
            r.raise_for_status()
            data = r.json()
            return {
                "status": data["status"],
                "conclusion": data["conclusion"],
                "url": data["html_url"],
            }

    @mcp.tool()
    async def github_list_recent_runs(repo: str, limit: int = 10) -> list:
        """List the most recent workflow runs for a repo."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"https://api.github.com/repos/{repo}/actions/runs?per_page={limit}",
                headers=_gh_headers(),
            )
            r.raise_for_status()
            return [
                {
                    "id": run["id"],
                    "name": run["name"],
                    "status": run["status"],
                    "conclusion": run["conclusion"],
                }
                for run in r.json()["workflow_runs"]
            ]

    @mcp.tool()
    async def github_get_run_logs(repo: str, run_id: str) -> str:
        """Fetch the logs for a workflow run (truncated to 10k chars)."""
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(
                f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/logs",
                headers=_gh_headers(),
            )
            r.raise_for_status()
            return r.text[:10000]
