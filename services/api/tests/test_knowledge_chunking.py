"""Tests for knowledge_service.chunk_text — token-aware chunker."""

from __future__ import annotations


def _chunk(text: str, **kw):
    from flow.application.knowledge_service import chunk_text

    return chunk_text(text, **kw)


def test_empty_returns_empty():
    assert _chunk("") == []
    assert _chunk("   ") == []


def test_short_text_single_chunk():
    result = _chunk("Hello world.")
    assert len(result) == 1
    assert "Hello world" in result[0]


def test_long_text_splits_into_multiple_chunks():
    # 500 tokens of text -> should split into multiple chunks at max_tokens=400
    long = " ".join([f"word{i}" for i in range(600)])
    result = _chunk(long, max_tokens=100, overlap_tokens=15)
    assert len(result) > 1


def test_overlap_produces_shared_content():
    # Each chunk should share ~overlap_tokens tokens with the next
    long = " ".join([f"word{i}" for i in range(300)])
    result = _chunk(long, max_tokens=80, overlap_tokens=20)
    assert len(result) >= 2
    # Overlap: last word(s) of chunk[i] appear at start of chunk[i+1]
    last_words_of_first = result[0].split()[-5:]
    first_words_of_second = result[1].split()[:15]
    overlap = set(last_words_of_first) & set(first_words_of_second)
    assert len(overlap) > 0, "Expected token overlap between consecutive chunks"


def test_hard_cap_respected():
    from flow.application.knowledge_service import _CHUNK_HARD_CAP

    # Generate text that would produce > _CHUNK_HARD_CAP chunks at small size
    huge = " ".join([f"w{i}" for i in range(_CHUNK_HARD_CAP * 10)])
    result = _chunk(huge, max_tokens=5, overlap_tokens=1)
    assert len(result) <= _CHUNK_HARD_CAP


def test_chunks_are_non_empty_strings():
    text = "Para one.\n\nPara two.\n\nPara three."
    result = _chunk(text)
    for chunk in result:
        assert isinstance(chunk, str)
        assert chunk.strip()
