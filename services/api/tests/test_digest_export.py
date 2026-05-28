"""Tests for Obsidian export — path traversal guard + safe write."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


def test_path_traversal_guard_rejects_escape():
    """_safe_write must raise ValueError when path escapes vault root."""
    from flow.interfaces.http.routes.digest import _safe_write

    with tempfile.TemporaryDirectory() as vault:
        with pytest.raises(ValueError, match="path traversal"):
            _safe_write(Path(vault), "../../etc/passwd", "malicious content")


def test_safe_write_creates_file_and_dirs():
    """_safe_write creates parent directories and writes content."""
    from flow.interfaces.http.routes.digest import _safe_write

    with tempfile.TemporaryDirectory() as vault:
        _safe_write(Path(vault), "Research/Digest/2026-05-28/paper.md", "# Hello")
        target = Path(vault) / "Research/Digest/2026-05-28/paper.md"
        assert target.exists()
        assert target.read_text() == "# Hello"


def test_safe_write_rejects_absolute_path():
    """_safe_write must reject absolute note_path values."""
    from flow.interfaces.http.routes.digest import _safe_write

    with tempfile.TemporaryDirectory() as vault:
        with pytest.raises(ValueError):
            _safe_write(Path(vault), "/etc/passwd", "bad")
