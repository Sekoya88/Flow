"""Add SKILL.md format columns to agent_skills

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE agent_skills ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE agent_skills ADD COLUMN IF NOT EXISTS allowed_tools TEXT[] NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE agent_skills ADD COLUMN IF NOT EXISTS triggers TEXT[] NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE agent_skills ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'")


def downgrade() -> None:
    op.execute("ALTER TABLE agent_skills DROP COLUMN IF EXISTS metadata")
    op.execute("ALTER TABLE agent_skills DROP COLUMN IF EXISTS triggers")
    op.execute("ALTER TABLE agent_skills DROP COLUMN IF EXISTS allowed_tools")
    op.execute("ALTER TABLE agent_skills DROP COLUMN IF EXISTS description")
