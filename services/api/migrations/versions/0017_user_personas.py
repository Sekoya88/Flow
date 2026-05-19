"""Add user_personas table — SOUL.md identity injected as system-prompt slot #1.

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-16
"""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE user_personas (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            user_id      UUID NOT NULL REFERENCES users(id)      ON DELETE CASCADE,
            content_md   TEXT NOT NULL DEFAULT '',
            version      INT  NOT NULL DEFAULT 1,
            derived_from JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX idx_user_personas_unique ON user_personas (workspace_id, user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_user_personas_unique")
    op.execute("DROP TABLE IF EXISTS user_personas")
