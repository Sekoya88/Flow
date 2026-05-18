"""Autonomous self-improvement mode — auto_improve_threshold + rollback_delta on agents.

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-18
"""
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULL = manual approval (current behavior preserved for existing agents)
    # 0.0–1.0 = auto-approve when A/B reward_delta >= threshold
    op.execute(
        """
        ALTER TABLE agents
          ADD COLUMN IF NOT EXISTS auto_improve_threshold REAL DEFAULT NULL,
          ADD COLUMN IF NOT EXISTS auto_improve_rollback_delta REAL DEFAULT 0.15
        """
    )

    # Track which auto-promotions are pending safety evaluation
    op.execute(
        """
        ALTER TABLE agent_versions
          ADD COLUMN IF NOT EXISTS auto_promoted_at TIMESTAMPTZ DEFAULT NULL,
          ADD COLUMN IF NOT EXISTS safety_eval_passed BOOLEAN DEFAULT NULL
        """
    )

    # Allow 'auto_approved' status on proposals (audit trail for autonomous activations)
    op.execute(
        """
        ALTER TABLE proposals
          ADD COLUMN IF NOT EXISTS auto_approved BOOLEAN NOT NULL DEFAULT FALSE
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE proposals DROP COLUMN IF EXISTS auto_approved")
    op.execute("ALTER TABLE agent_versions DROP COLUMN IF EXISTS safety_eval_passed")
    op.execute("ALTER TABLE agent_versions DROP COLUMN IF EXISTS auto_promoted_at")
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS auto_improve_rollback_delta")
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS auto_improve_threshold")
