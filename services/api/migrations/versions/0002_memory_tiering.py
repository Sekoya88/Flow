"""memory_tiering

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-27
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Episodic memory — per-thread run summaries, promoted from working memory by synthesizer
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS episodic_memories (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
            agent_id UUID NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            execution_id UUID REFERENCES executions (id) ON DELETE SET NULL,
            content TEXT NOT NULL,
            embedding vector(1536),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_episodic_memories_lookup "
        "ON episodic_memories (workspace_id, agent_id, user_id)"
    )

    # Agent negatives — workspace-level negative examples (rejected proposals, low-score runs)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_negatives (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
            agent_id UUID NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'feedback',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agent_negatives_lookup "
        "ON agent_negatives (workspace_id, agent_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_negatives")
    op.execute("DROP TABLE IF EXISTS episodic_memories")
