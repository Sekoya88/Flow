"""Knowledge ingest correctness — status must reflect partial-write failures."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flow.application.knowledge_service import ingest_document


@pytest.mark.asyncio
async def test_ingest_marks_source_failed_when_chunk_insert_fails_mid_loop() -> None:
    """If chunk N>0 fails after prior chunks were written, source must not stay 'processing'."""
    source_id = uuid.UUID("00000000-0000-4000-8000-000000000001")
    workspace_id = uuid.UUID("00000000-0000-4000-8000-000000000002")
    repo = MagicMock()
    repo.insert_knowledge_source = AsyncMock(return_value=source_id)
    repo.set_knowledge_ingest = AsyncMock()
    repo.insert_chunk = AsyncMock(side_effect=[1, RuntimeError("simulated DB failure")])

    # Two paragraphs under one chunk max still merge into one chunk; force two chunks.
    para = "x" * 900
    body = f"{para}\n\n{para}"

    with patch(
        "flow.application.knowledge_service.emb_svc.embed_texts",
        new_callable=AsyncMock,
        return_value=[[0.01] * 8, [0.02] * 8],
    ):
        with pytest.raises(RuntimeError, match="simulated DB"):
            await ingest_document(
                repo=repo,
                openai_api_key="sk-test",
                workspace_id=workspace_id,
                title="t",
                body=body,
                settings=None,
            )

    repo.set_knowledge_ingest.assert_called_once()
    call = repo.set_knowledge_ingest.call_args
    assert call[0][0] == source_id
    assert call[0][1] == "failed"
    assert "simulated DB" in (call[0][2] or "")
