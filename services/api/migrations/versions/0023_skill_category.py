"""Add category column to agent_skills.

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-21
"""

from alembic import op

revision: str = "0023"
down_revision: str = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE agent_skills ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'General'"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agent_skills_category ON agent_skills (workspace_id, category)"
    )
    # Backfill from metadata JSONB where already set
    op.execute(
        """
        UPDATE agent_skills
        SET category = metadata->>'category'
        WHERE metadata->>'category' IS NOT NULL
          AND metadata->>'category' <> ''
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_agent_skills_category")
    op.execute("ALTER TABLE agent_skills DROP COLUMN IF EXISTS category")
