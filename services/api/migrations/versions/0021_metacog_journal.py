"""MetaCog journal + skill_scores tables.

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-19
"""

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Metacognitive journal — one row per execution reflection
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS metacog_journal (
            id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_id          UUID        NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            workspace_id      UUID        NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            execution_id      UUID        REFERENCES executions(id) ON DELETE SET NULL,
            grade             SMALLINT    NOT NULL CHECK (grade BETWEEN 1 AND 5),
            prediction        TEXT,
            calibration_error REAL,
            skill_scores      JSONB       NOT NULL DEFAULT '[]'::jsonb,
            mutations_proposed JSONB      NOT NULL DEFAULT '[]'::jsonb,
            reasoning         TEXT,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_metacog_journal_agent ON metacog_journal (agent_id, created_at DESC)")
    op.execute("CREATE INDEX idx_metacog_journal_exec ON metacog_journal (execution_id) WHERE execution_id IS NOT NULL")

    # Per-skill contribution scores (denormalized from journal for fast queries)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS skill_contribution_scores (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            skill_id     UUID        NOT NULL REFERENCES agent_skills(id) ON DELETE CASCADE,
            execution_id UUID        REFERENCES executions(id) ON DELETE SET NULL,
            agent_id     UUID        NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            contribution REAL        NOT NULL,
            rationale    TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_skill_contrib_skill ON skill_contribution_scores (skill_id, created_at DESC)")
    op.execute("CREATE INDEX idx_skill_contrib_agent ON skill_contribution_scores (agent_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_skill_contrib_agent")
    op.execute("DROP INDEX IF EXISTS idx_skill_contrib_skill")
    op.execute("DROP TABLE IF EXISTS skill_contribution_scores")
    op.execute("DROP INDEX IF EXISTS idx_metacog_journal_exec")
    op.execute("DROP INDEX IF EXISTS idx_metacog_journal_agent")
    op.execute("DROP TABLE IF EXISTS metacog_journal")
