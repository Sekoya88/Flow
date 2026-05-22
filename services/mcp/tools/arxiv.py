from __future__ import annotations

from datetime import datetime, timedelta


def register_arxiv_tools(mcp):  # type: ignore[no-untyped-def]

    @mcp.tool()
    async def arxiv_search(
        query: str,
        categories: list[str] | None = None,
        max_results: int = 10,
        days_back: int = 1,
    ) -> list:
        """Search recent arXiv papers.
        categories e.g. ['cs.AI', 'cs.LG', 'cs.CL', 'stat.ML']
        Returns papers from the last days_back days."""
        import arxiv

        cats = categories or ["cs.AI", "cs.LG"]
        cutoff = datetime.now() - timedelta(days=days_back)
        cat_query = " OR ".join(f"cat:{c}" for c in cats)
        full_query = f"({query}) AND ({cat_query})" if query else cat_query

        search = arxiv.Search(
            query=full_query,
            max_results=max_results * 3,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )

        results = []
        try:
            for paper in search.results():
                if paper.published.replace(tzinfo=None) < cutoff:
                    continue
                results.append({
                    "title": paper.title,
                    "authors": [str(a) for a in paper.authors[:5]],
                    "abstract": paper.summary[:500],
                    "arxiv_id": paper.get_short_id(),
                    "url": paper.entry_id,
                    "pdf_url": paper.pdf_url,
                    "categories": paper.categories,
                    "published": paper.published.isoformat(),
                })
                if len(results) >= max_results:
                    break
        except Exception as e:
            raise RuntimeError(f"arXiv search failed: {e}") from e

        return results

    @mcp.tool()
    async def arxiv_fetch_abstract(arxiv_id: str) -> dict:
        """Fetch full abstract and metadata for an arXiv paper by ID."""
        import arxiv

        try:
            search = arxiv.Search(id_list=[arxiv_id])
            for paper in search.results():
                return {
                    "title": paper.title,
                    "authors": [str(a) for a in paper.authors],
                    "abstract": paper.summary,
                    "arxiv_id": paper.get_short_id(),
                    "url": paper.entry_id,
                    "pdf_url": paper.pdf_url,
                    "categories": paper.categories,
                    "published": paper.published.isoformat(),
                    "updated": paper.updated.isoformat(),
                }
        except Exception as e:
            raise RuntimeError(f"arXiv fetch failed: {e}") from e

        return {}
