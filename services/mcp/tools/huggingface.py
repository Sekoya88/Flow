from __future__ import annotations

import httpx


def register_huggingface_tools(mcp):  # type: ignore[no-untyped-def]

    @mcp.tool()
    async def hf_search_papers(date: str = "today", limit: int = 20) -> list:
        """Scrape HuggingFace Daily Papers.
        date = 'today' or 'YYYY-MM-DD'.
        Returns list of {title, authors, abstract, url, upvotes, arxiv_id}."""
        from bs4 import BeautifulSoup

        url = "https://huggingface.co/papers"
        if date != "today":
            url = f"https://huggingface.co/papers?date={date}"

        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": "FlowResearchDigest/1.0"},
                timeout=30.0,
                follow_redirects=True,
            ) as client:
                r = await client.get(url)
                r.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeError(f"HuggingFace papers fetch failed: {e}") from e

        soup = BeautifulSoup(r.text, "html.parser")
        papers = []
        for article in soup.select("article")[:limit]:
            title_el = article.select_one("h3 a")
            if not title_el:
                continue
            paper: dict = {
                "title": title_el.get_text(strip=True),
                "url": f"https://huggingface.co{title_el.get('href', '')}",
                "abstract": "",
                "authors": [],
                "upvotes": 0,
                "arxiv_id": "",
            }
            abstract_el = article.select_one("p")
            if abstract_el:
                paper["abstract"] = abstract_el.get_text(strip=True)
            upvotes_el = article.select_one("[data-upvotes]")
            if upvotes_el:
                paper["upvotes"] = int(upvotes_el.get("data-upvotes", 0))
            papers.append(paper)

        return papers

    @mcp.tool()
    async def hf_get_paper_details(paper_url: str) -> dict:
        """Get full details for a HuggingFace paper (abstract, authors, arXiv links)."""
        from bs4 import BeautifulSoup

        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": "FlowResearchDigest/1.0"},
                timeout=30.0,
                follow_redirects=True,
            ) as client:
                r = await client.get(paper_url)
                r.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeError(f"Paper fetch failed: {e}") from e

        soup = BeautifulSoup(r.text, "html.parser")
        details: dict = {
            "url": paper_url,
            "title": "",
            "abstract": "",
            "authors": [],
            "arxiv_id": "",
            "arxiv_url": "",
        }
        title_el = soup.select_one("h1")
        if title_el:
            details["title"] = title_el.get_text(strip=True)
        abstract_el = soup.select_one(".prose p")
        if abstract_el:
            details["abstract"] = abstract_el.get_text(strip=True)
        arxiv_link = soup.select_one('a[href*="arxiv.org/abs"]')
        if arxiv_link:
            details["arxiv_url"] = arxiv_link["href"]
            details["arxiv_id"] = arxiv_link["href"].split("/abs/")[-1]
        return details
