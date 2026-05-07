"""add agent_skills table

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_skills (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_id UUID NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
            workspace_id UUID NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            version INT NOT NULL DEFAULT 1,
            content_md TEXT NOT NULL,
            active BOOLEAN NOT NULL DEFAULT true,
            score REAL NOT NULL DEFAULT 1.0,
            use_count INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_agent_skills_active
            ON agent_skills (agent_id, workspace_id, active);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_skills;")
