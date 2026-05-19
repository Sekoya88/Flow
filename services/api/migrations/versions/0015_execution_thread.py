"""Add thread_id to executions for multi-turn conversation resume.

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-15
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE executions ADD COLUMN thread_id UUID")
    op.execute("UPDATE executions SET thread_id = id WHERE thread_id IS NULL")
    op.execute("CREATE INDEX idx_executions_thread_id ON executions (thread_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_executions_thread_id")
    op.execute("ALTER TABLE executions DROP COLUMN IF EXISTS thread_id")
