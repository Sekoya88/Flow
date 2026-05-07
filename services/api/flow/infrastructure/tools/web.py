"""Web-facing tools: Tavily search, webpage fetch, ArXiv search, HuggingFace papers."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx
from bs4 import BeautifulSoup


async def run_tavily_search(query: str, max_results: int = 5, api_key: str = "") -> list[dict]:
    if not api_key:
        return [{"error": "FLOW_TAVILY_API_KEY not configured"}]
    from tavily import AsyncTavilyClient  # type: ignore[import-untyped]
    client = AsyncTavilyClient(api_key=api_key)
    response = await client.search(query, max_results=max_results)
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", "")[:600],
        }
        for r in response.get("results", [])
    ]


async def run_fetch_webpage(url: str) -> str:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 FlowBot/1.0"})
        resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    lines = [ln for ln in soup.get_text(separator="\n", strip=True).splitlines() if ln.strip()]
    return "\n".join(lines)[:8000]


async def run_arxiv_search(query: str, max_results: int = 5) -> list[dict]:
    url = (
        f"https://export.arxiv.org/api/query"
        f"?search_query=all:{query}&max_results={max_results}"
        f"&sortBy=submittedDate&sortOrder=descending"
    )
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url)
    root = ET.fromstring(resp.text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    return [
        {
            "title": (entry.findtext("atom:title", "", ns) or "").strip(),
            "abstract": (entry.findtext("atom:summary", "", ns) or "").strip()[:600],
            "url": (entry.findtext("atom:id", "", ns) or "").strip(),
            "published": (entry.findtext("atom:published", "", ns) or "").strip(),
        }
        for entry in root.findall("atom:entry", ns)
    ]


async def run_hf_papers(date: str = "") -> list[dict]:
    url = "https://huggingface.co/api/daily_papers"
    if date:
        url += f"?date={date}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
    data = resp.json()
    papers = []
    for item in (data if isinstance(data, list) else [])[:20]:
        paper = item.get("paper", {})
        papers.append({
            "title": paper.get("title", ""),
            "abstract": paper.get("summary", "")[:600],
            "url": f"https://huggingface.co/papers/{paper.get('id', '')}",
            "published": paper.get("publishedAt", ""),
            "upvotes": item.get("totalVotes", 0),
        })
    return papers
