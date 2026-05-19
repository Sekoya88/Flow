"""Add prompt_hash to agent_versions for byte-stable prompt verification.

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-15
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE agent_versions ADD COLUMN IF NOT EXISTS prompt_hash CHAR(64)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_versions_prompt_hash ON agent_versions (prompt_hash)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_agent_versions_prompt_hash")
    op.execute("ALTER TABLE agent_versions DROP COLUMN IF EXISTS prompt_hash")
