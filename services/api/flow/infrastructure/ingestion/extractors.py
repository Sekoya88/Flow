from __future__ import annotations

import io


def extract_pdf(raw: bytes) -> str:
    """Extract plain text from PDF bytes using PyMuPDF."""
    import pymupdf  # fitz

    doc = pymupdf.open(stream=raw, filetype="pdf")
    pages: list[str] = []
    for page in doc:
        pages.append(page.get_text())
    return "\n\n".join(p.strip() for p in pages if p.strip())


def extract_docx(raw: bytes) -> str:
    """Extract plain text from .docx bytes."""
    from docx import Document

    doc = Document(io.BytesIO(raw))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def extract_url_content(url: str, *, timeout: int = 15) -> str:
    """Fetch URL and extract main body text, stripping nav/footer/script."""
    import httpx
    from bs4 import BeautifulSoup

    resp = httpx.get(url, timeout=timeout, follow_redirects=True, headers={"User-Agent": "FlowBot/1.0"})
    if hasattr(resp, "raise_for_status"):
        resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["nav", "footer", "header", "script", "style", "aside"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body
    if main is None:
        return ""
    text = main.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n\n".join(lines)
