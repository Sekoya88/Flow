"""Add UNIQUE (workspace_id, title) to digest_papers for ON CONFLICT deduplication.

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-22
"""

from alembic import op

revision: str = "0027"
down_revision: str = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE digest_papers
        ADD CONSTRAINT digest_papers_workspace_title_key
        UNIQUE (workspace_id, title)
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE digest_papers DROP CONSTRAINT IF EXISTS digest_papers_workspace_title_key")
