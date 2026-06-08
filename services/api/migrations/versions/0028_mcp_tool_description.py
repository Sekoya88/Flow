"""Add description column to mcp_server_tool_assignments.

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-26
"""

from alembic import op

revision: str = "0028"
down_revision: str = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE mcp_server_tool_assignments ADD COLUMN IF NOT EXISTS description TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE mcp_server_tool_assignments DROP COLUMN IF EXISTS description")
