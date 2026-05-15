"""Tests for byte-stable prompt hashing."""
from __future__ import annotations

from langchain_core.messages import SystemMessage

from flow.application.prompt_hash import compute_prompt_hash


def test_hash_empty_returns_empty_string():
    assert compute_prompt_hash(None) == ""


def test_hash_is_deterministic_for_string():
    a = compute_prompt_hash("You are a helpful agent.")
    b = compute_prompt_hash("You are a helpful agent.")
    assert a == b
    assert len(a) == 64


def test_hash_differs_for_different_strings():
    a = compute_prompt_hash("You are a helpful agent.")
    b = compute_prompt_hash("You are a sarcastic agent.")
    assert a != b


def test_anthropic_cache_block_yields_same_hash_as_raw_string():
    """Wrapping a prompt for Anthropic cache_control must NOT change its hash."""
    raw = "You are a helpful agent."
    wrapped = [{"type": "text", "text": raw, "cache_control": {"type": "ephemeral"}}]
    assert compute_prompt_hash(raw) == compute_prompt_hash(wrapped)


def test_hash_handles_system_message_object():
    msg = SystemMessage(content="You are a helpful agent.")
    h = compute_prompt_hash(msg)
    assert len(h) == 64


def test_hash_stable_across_calls():
    """Same prompt across many calls = same hash. Anchors the prefix-cache contract."""
    prompt = "Multi-line\nprompt\nwith details."
    hashes = {compute_prompt_hash(prompt) for _ in range(50)}
    assert len(hashes) == 1
