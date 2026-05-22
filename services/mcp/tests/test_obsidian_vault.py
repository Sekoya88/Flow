"""Tests for LocalVaultService — filesystem vault operations."""
from __future__ import annotations

import pytest

from vault.local_vault import LocalVaultService


@pytest.fixture
def vault(tmp_path):
    return LocalVaultService(str(tmp_path / "vault"))


@pytest.mark.asyncio
async def test_create_note_writes_file(vault, tmp_path):
    """create_note writes content to the correct path under vault root."""
    path = await vault.create_note("research/paper.md", "# Hello")
    assert "paper.md" in path
    content = (tmp_path / "vault" / "research" / "paper.md").read_text()
    assert "# Hello" in content


@pytest.mark.asyncio
async def test_create_note_with_frontmatter(vault, tmp_path):
    """create_note prepends YAML frontmatter when provided."""
    await vault.create_note("note.md", "body", frontmatter={"title": "Test", "status": "unread"})
    content = (tmp_path / "vault" / "note.md").read_text()
    assert "---" in content
    assert "title: Test" in content
    assert "body" in content


@pytest.mark.asyncio
async def test_read_note_returns_content(vault):
    """read_note returns the written content."""
    await vault.create_note("test.md", "Hello World")
    content = await vault.read_note("test.md")
    assert "Hello World" in content


@pytest.mark.asyncio
async def test_read_note_missing_returns_empty(vault):
    """read_note returns empty string for nonexistent path."""
    result = await vault.read_note("nonexistent/note.md")
    assert result == ""


@pytest.mark.asyncio
async def test_append_note_adds_content(vault):
    """append_note appends to existing note."""
    await vault.create_note("append.md", "First line")
    ok = await vault.append_note("append.md", "Second line")
    assert ok is True
    content = await vault.read_note("append.md")
    assert "First line" in content
    assert "Second line" in content


@pytest.mark.asyncio
async def test_append_note_missing_returns_false(vault):
    """append_note returns False when note does not exist."""
    ok = await vault.append_note("missing.md", "data")
    assert ok is False


@pytest.mark.asyncio
async def test_list_notes_empty(vault):
    """list_notes returns empty list when vault has no .md files."""
    result = await vault.list_notes()
    assert result == []


@pytest.mark.asyncio
async def test_list_notes_finds_created_notes(vault):
    """list_notes returns relative paths of all .md files."""
    await vault.create_note("a/note1.md", "a")
    await vault.create_note("b/note2.md", "b")
    notes = await vault.list_notes()
    assert len(notes) == 2
    assert any("note1.md" in n for n in notes)
    assert any("note2.md" in n for n in notes)


@pytest.mark.asyncio
async def test_list_notes_prefix_filter(vault):
    """list_notes with prefix only returns notes under that path."""
    await vault.create_note("a/note1.md", "a")
    await vault.create_note("b/note2.md", "b")
    notes = await vault.list_notes(prefix="a")
    assert all("note1.md" in n for n in notes)
    assert not any("note2.md" in n for n in notes)


@pytest.mark.asyncio
async def test_create_note_creates_parent_dirs(vault, tmp_path):
    """create_note creates nested parent directories as needed."""
    await vault.create_note("deep/nested/dir/note.md", "content")
    assert (tmp_path / "vault" / "deep" / "nested" / "dir" / "note.md").exists()
