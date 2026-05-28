"""Link project_runs to digest_runs via digest_run_id

Revision ID: 0035
Revises: 0034
Create Date: 2026-05-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0035"
down_revision: str | Sequence[str] | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE project_runs
        ADD COLUMN IF NOT EXISTS digest_run_id UUID REFERENCES digest_runs(id) ON DELETE SET NULL;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE project_runs DROP COLUMN IF EXISTS digest_run_id;")
