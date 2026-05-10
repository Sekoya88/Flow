"""Add eval_run_id to golden_results for per-run history grouping

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE golden_results
            ADD COLUMN IF NOT EXISTS eval_run_id UUID
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_golden_results_run
            ON golden_results (eval_run_id)
            WHERE eval_run_id IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_golden_results_agent_version
            ON golden_results (agent_id, agent_version_label, created_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_golden_results_agent_version")
    op.execute("DROP INDEX IF EXISTS idx_golden_results_run")
    op.execute("ALTER TABLE golden_results DROP COLUMN IF EXISTS eval_run_id")
