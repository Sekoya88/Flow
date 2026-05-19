

def test_parses_frontmatter():
    """should extract YAML frontmatter as dict"""
    from flow.application.kg_parser import ObsidianDocument, parse_obsidian_note
    doc = ObsidianDocument(
        filename="AI/Test.md",
        raw_content="---\ntags: [agents, llm]\ncreated: 2026-01-01\n---\n# Test\nBody text.",
        source="upload",
    )
    result = parse_obsidian_note(doc)
    assert result.frontmatter["tags"] == ["agents", "llm"]
    assert result.body == "Body text."


def test_parses_wikilinks():
    """should extract [[wikilink]] targets"""
    from flow.application.kg_parser import ObsidianDocument, parse_obsidian_note
    doc = ObsidianDocument(
        filename="note.md",
        raw_content="See [[LangChain]] and [[RAG Systems|RAG]] for more.",
        source="upload",
    )
    result = parse_obsidian_note(doc)
    assert "LangChain" in result.wikilinks
    assert "RAG Systems" in result.wikilinks


def test_parses_tags():
    """should extract #tags from body (not inside code blocks)"""
    from flow.application.kg_parser import ObsidianDocument, parse_obsidian_note
    doc = ObsidianDocument(
        filename="note.md",
        raw_content="Notes on #agents and #llm/prompting.\n```\n#not-a-tag\n```",
        source="upload",
    )
    result = parse_obsidian_note(doc)
    assert "agents" in result.tags
    assert "llm/prompting" in result.tags
    assert "not-a-tag" not in result.tags


def test_content_hash_is_sha256():
    """should produce stable SHA-256 hex digest"""
    import hashlib

    from flow.application.kg_parser import ObsidianDocument, parse_obsidian_note
    content = "Hello world"
    doc = ObsidianDocument(filename="x.md", raw_content=content, source="upload")
    result = parse_obsidian_note(doc)
    expected = hashlib.sha256(content.encode()).hexdigest()
    assert result.content_hash == expected


def test_title_from_h1():
    """should use H1 heading as title when present"""
    from flow.application.kg_parser import ObsidianDocument, parse_obsidian_note
    doc = ObsidianDocument(
        filename="folder/note.md",
        raw_content="# My Note Title\nContent here.",
        source="upload",
    )
    result = parse_obsidian_note(doc)
    assert result.title == "My Note Title"


def test_title_fallback_to_filename():
    """should use filename stem as title when no H1"""
    from flow.application.kg_parser import ObsidianDocument, parse_obsidian_note
    doc = ObsidianDocument(
        filename="folder/my-note.md",
        raw_content="Some content without a heading.",
        source="upload",
    )
    result = parse_obsidian_note(doc)
    assert result.title == "my-note"
