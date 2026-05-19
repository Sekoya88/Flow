from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel


class ObsidianDocument(BaseModel):
    filename: str
    raw_content: str
    source: Literal["upload", "api", "sync"]


class ParsedNote(BaseModel):
    filename: str
    title: str
    frontmatter: dict[str, Any]
    tags: list[str]
    wikilinks: list[str]
    body: str
    content_hash: str


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]+)?\]\]")
_TAG_RE = re.compile(r"(?<![`\w])#([a-zA-Z][a-zA-Z0-9_/\-]*)")
_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)


def parse_obsidian_note(doc: ObsidianDocument) -> ParsedNote:
    content = doc.raw_content
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    # Extract frontmatter
    frontmatter: dict[str, Any] = {}
    body = content
    fm_match = _FRONTMATTER_RE.match(content)
    if fm_match:
        try:
            import yaml

            frontmatter = yaml.safe_load(fm_match.group(1)) or {}
        except Exception:
            frontmatter = {}
        body = content[fm_match.end() :]

    # Extract wikilinks before stripping markup
    wikilinks = list(dict.fromkeys(_WIKILINK_RE.findall(body)))

    # Strip code blocks before tag extraction to avoid false positives
    body_no_code = _CODE_BLOCK_RE.sub("", body)
    tags = list(dict.fromkeys(_TAG_RE.findall(body_no_code)))

    # Clean body: remove wikilink brackets, keep display text
    clean_body = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", body)
    clean_body = clean_body.strip()

    # Title: first H1 heading or filename stem
    h1 = _H1_RE.search(clean_body)
    if h1:
        title = h1.group(1).strip()
        # Remove H1 line from body
        clean_body = clean_body[: h1.start()].strip() + "\n" + clean_body[h1.end() :].strip()
        clean_body = clean_body.strip()
    else:
        title = Path(doc.filename).stem

    return ParsedNote(
        filename=doc.filename,
        title=title,
        frontmatter=frontmatter,
        tags=tags,
        wikilinks=wikilinks,
        body=clean_body,
        content_hash=content_hash,
    )
