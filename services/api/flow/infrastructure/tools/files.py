"""File-handling tools: file_read, pdf_extract."""
from __future__ import annotations


async def run_file_read(path: str, encoding: str = "utf-8") -> str:
    """Read a local file by path and return its text content (truncated to 32KB)."""
    try:
        with open(path, encoding=encoding, errors="replace") as fh:
            return fh.read(32768)
    except FileNotFoundError:
        return f"[error: file not found: {path}]"
    except Exception as exc:
        return f"[error reading file: {exc}]"


async def run_pdf_extract(path: str) -> dict:
    """Extract structured text from a PDF: sections, page count, and raw text.

    Returns a dict with keys: pages (int), text (str), sections (list[str]).
    Falls back gracefully if pdfminer/pypdf are unavailable.
    """
    text_blocks: list[str] = []
    page_count = 0

    try:
        import pypdf  # type: ignore[import-untyped]

        with open(path, "rb") as fh:
            reader = pypdf.PdfReader(fh)
            page_count = len(reader.pages)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_blocks.append(page_text)
    except ImportError:
        # Try pdfminer as fallback
        try:
            from pdfminer.high_level import extract_text as pdfminer_extract  # type: ignore[import-untyped]

            full_text = pdfminer_extract(path)
            text_blocks = [full_text]
            page_count = full_text.count("\x0c") + 1
        except ImportError:
            return {"pages": 0, "text": "[error: install pypdf or pdfminer.six to use pdf_extract]", "sections": []}
    except FileNotFoundError:
        return {"pages": 0, "text": f"[error: file not found: {path}]", "sections": []}
    except Exception as exc:
        return {"pages": 0, "text": f"[error: {exc}]", "sections": []}

    full_text = "\n".join(text_blocks)
    # Detect section headings: lines that are short, title-cased or ALL-CAPS
    sections = [
        ln.strip()
        for ln in full_text.splitlines()
        if ln.strip() and len(ln.strip()) < 120 and (ln.strip().istitle() or ln.strip().isupper())
    ][:50]

    return {
        "pages": page_count,
        "text": full_text[:16000],
        "sections": sections,
    }
