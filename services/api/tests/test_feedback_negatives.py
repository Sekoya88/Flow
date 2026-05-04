from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock


def test_low_score_inserts_negative():
    """When score < 0.5, feedback route should insert agent negative."""
    from flow.interfaces.http.routes.feedback import _maybe_insert_negative

    repo = MagicMock()
    repo.insert_agent_negative = AsyncMock(return_value=uuid.uuid4())

    asyncio.get_event_loop().run_until_complete(
        _maybe_insert_negative(
            repo=repo,
            execution_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            user_message="What is Flow?",
            score=0.3,
        )
    )
    repo.insert_agent_negative.assert_called_once()


def test_high_score_skips_negative():
    """When score >= 0.5, no negative should be inserted."""
    from flow.interfaces.http.routes.feedback import _maybe_insert_negative

    repo = MagicMock()
    repo.insert_agent_negative = AsyncMock()

    asyncio.get_event_loop().run_until_complete(
        _maybe_insert_negative(
            repo=repo,
            execution_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            user_message="What is Flow?",
            score=0.8,
        )
    )
    repo.insert_agent_negative.assert_not_called()
