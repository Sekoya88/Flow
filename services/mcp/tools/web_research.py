from __future__ import annotations

import httpx

from ..config import settings


def register_web_research_tools(mcp):  # type: ignore[no-untyped-def]

    @mcp.tool()
    async def web_crawl_article(url: str) -> dict:
        """Crawl and extract clean content from an article URL.
        Uses trafilatura. Returns title, text, author, date."""
        import trafilatura

        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                headers={"User-Agent": "FlowResearchDigest/1.0"},
                follow_redirects=True,
            ) as client:
                r = await client.get(url)
                r.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeError(f"Article fetch failed: {e}") from e

        text = trafilatura.extract(r.text, include_comments=False, include_tables=True)
        metadata = trafilatura.extract_metadata(r.text)
        return {
            "url": url,
            "title": metadata.title if metadata else "",
            "text": text or "",
            "author": metadata.author if metadata else "",
            "date": str(metadata.date) if metadata and metadata.date else "",
            "description": metadata.description if metadata else "",
        }

    @mcp.tool()
    async def web_search_tavily(query: str, max_results: int = 5) -> list:
        """Web search via Tavily (if API key set) or DuckDuckGo fallback."""
        if settings.tavily_api_key:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    r = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": settings.tavily_api_key,
                            "query": query,
                            "max_results": max_results,
                        },
                    )
                    r.raise_for_status()
                    return r.json().get("results", [])
            except httpx.HTTPError as e:
                raise RuntimeError(f"Tavily search failed: {e}") from e
        else:
            try:
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=max_results))
            except Exception as e:
                raise RuntimeError(f"DuckDuckGo search failed: {e}") from e
