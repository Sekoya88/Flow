"""Skill observability — golden_items skill linkage + execution events table.

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-16
"""

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Link golden_items to the specific skill that they evaluate
    op.execute(
        """
        ALTER TABLE golden_items
          ADD COLUMN IF NOT EXISTS skill_id UUID NULL
            REFERENCES agent_skills(id) ON DELETE SET NULL
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_golden_items_skill ON golden_items (skill_id) WHERE skill_id IS NOT NULL")

    # Per-execution telemetry: which skill matched on which run
    op.execute(
        """
        CREATE TABLE skill_execution_events (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            skill_id     UUID        NOT NULL REFERENCES agent_skills(id) ON DELETE CASCADE,
            execution_id UUID        NULL      REFERENCES executions(id)  ON DELETE SET NULL,
            workspace_id UUID        NOT NULL REFERENCES workspaces(id)   ON DELETE CASCADE,
            matched_text TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_skill_exec_events_skill ON skill_execution_events (skill_id, created_at DESC)")
    op.execute("CREATE INDEX idx_skill_exec_events_exec ON skill_execution_events (execution_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_skill_exec_events_exec")
    op.execute("DROP INDEX IF EXISTS idx_skill_exec_events_skill")
    op.execute("DROP TABLE IF EXISTS skill_execution_events")
    op.execute("DROP INDEX IF EXISTS idx_golden_items_skill")
    op.execute("ALTER TABLE golden_items DROP COLUMN IF EXISTS skill_id")
