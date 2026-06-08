"""One-time dev tool: fetch curated baseline SKILL.md files into the vendored dir.

Usage:
  uv run python scripts/vendor_skills.py
Re-run to refresh. Output files are committed so seeding works offline.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from flow.infrastructure.persistence.skill_collections import (
    CURATED_COLLECTIONS,
    is_skill_file,
    raw_url,
)

VENDOR_DIR = Path(__file__).resolve().parent.parent / "flow" / "infrastructure" / "persistence" / "vendored_skills"


async def main() -> None:
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    written = skipped = 0
    async with httpx.AsyncClient(timeout=30) as http:
        for c in CURATED_COLLECTIONS:
            for s in c["skills"]:
                url = raw_url(c["repo"], s["path"])
                try:
                    r = await http.get(url)
                except httpx.RequestError as exc:
                    print(f"  ERR  {url}: {exc}")
                    skipped += 1
                    continue
                if r.status_code != 200 or not is_skill_file(s["path"], r.text):
                    print(f"  skip {url}: HTTP {r.status_code} / not a skill")
                    skipped += 1
                    continue
                out = VENDOR_DIR / f"{c['id']}__{s['name']}.md"
                out.write_text(r.text, encoding="utf-8")
                print(f"  ok   {out.name}")
                written += 1
    print(f"\nVendored {written} skills, skipped {skipped} -> {VENDOR_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
