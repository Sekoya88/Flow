from __future__ import annotations

import io
import pytest


def _make_pdf_bytes(text: str) -> bytes:
    """Minimal valid single-page PDF containing text."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_docx_bytes(text: str) -> bytes:
    from docx import Document
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_extract_pdf_returns_text():
    from flow.infrastructure.ingestion.extractors import extract_pdf
    raw = _make_pdf_bytes("Hello PDF world")
    result = extract_pdf(raw)
    assert "Hello PDF world" in result


def test_extract_docx_returns_text():
    from flow.infrastructure.ingestion.extractors import extract_docx
    raw = _make_docx_bytes("Hello docx world")
    result = extract_docx(raw)
    assert "Hello docx world" in result


def test_extract_pdf_empty_returns_empty():
    from flow.infrastructure.ingestion.extractors import extract_pdf
    import pymupdf
    doc = pymupdf.open()
    doc.new_page()
    buf = io.BytesIO()
    doc.save(buf)
    result = extract_pdf(buf.getvalue())
    assert result == ""


def test_extract_url_strips_nav(monkeypatch):
    from flow.infrastructure.ingestion.extractors import extract_url_content

    html = """
    <html><body>
      <nav>Skip me</nav>
      <main><p>Main content here</p></main>
      <footer>Also skip</footer>
    </body></html>
    """

    class FakeResp:
        status_code = 200
        text = html
        def raise_for_status(self): pass

    import httpx
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: FakeResp())

    result = extract_url_content("https://example.com")
    assert "Main content here" in result
    assert "Skip me" not in result


def test_extract_url_raises_on_http_error(monkeypatch):
    import httpx
    from flow.infrastructure.ingestion.extractors import extract_url_content

    class FakeErrorResp:
        status_code = 404
        text = "Not Found"
        def raise_for_status(self):
            raise httpx.HTTPStatusError("404", request=None, response=None)

    monkeypatch.setattr(httpx, "get", lambda *a, **kw: FakeErrorResp())
    with pytest.raises(httpx.HTTPStatusError):
        extract_url_content("https://example.com/missing")
