"""Add error_message column to skill_training_runs

Revision ID: 0032
Revises: 0031
Create Date: 2026-05-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0032"
down_revision: str | Sequence[str] | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE skill_training_runs
        ADD COLUMN IF NOT EXISTS error_message TEXT;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE skill_training_runs
        DROP COLUMN IF EXISTS error_message;
    """)
