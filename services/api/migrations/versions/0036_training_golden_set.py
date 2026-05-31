"""dataset-aware, per-item regression-gated skill training

Links a training run to the golden set it trained on, and stores per-item
before→after scores on each epoch so the regression gate is auditable.

Revision ID: 0036
Revises: 0035
Create Date: 2026-05-31
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0036"
down_revision: str | Sequence[str] | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE skill_training_runs
            ADD COLUMN IF NOT EXISTS golden_set_id UUID
                REFERENCES golden_sets(id) ON DELETE SET NULL;
    """)
    op.execute("""
        ALTER TABLE skill_training_epochs
            ADD COLUMN IF NOT EXISTS item_scores JSONB;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE skill_training_epochs DROP COLUMN IF EXISTS item_scores;")
    op.execute("ALTER TABLE skill_training_runs DROP COLUMN IF EXISTS golden_set_id;")
