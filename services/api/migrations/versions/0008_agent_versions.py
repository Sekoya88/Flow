"""create agent_versions table

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_versions (
            id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            agent_id    UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            version_label TEXT NOT NULL,
            config_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
            template    TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by  UUID REFERENCES users(id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_versions_agent ON agent_versions (agent_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_versions")
