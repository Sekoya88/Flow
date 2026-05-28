"""Add skill_training_events table for live COT visibility during training runs

Revision ID: 0034
Revises: 0033
Create Date: 2026-05-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0034"
down_revision: str | Sequence[str] | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS skill_training_events (
            id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id     UUID        NOT NULL REFERENCES skill_training_runs(id) ON DELETE CASCADE,
            stage      TEXT        NOT NULL,
            kind       TEXT        NOT NULL,
            message    TEXT        NOT NULL,
            data       JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS skill_training_events_run_idx
        ON skill_training_events (run_id, created_at);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS skill_training_events_run_idx;")
    op.execute("DROP TABLE IF EXISTS skill_training_events;")
