"""Skill bandit arms table for Thompson Sampling.

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-19
"""

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS skill_bandit_arms (
            skill_id     UUID        NOT NULL REFERENCES agent_skills(id) ON DELETE CASCADE,
            agent_id     UUID        NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            alpha        REAL        NOT NULL DEFAULT 1.0,
            beta         REAL        NOT NULL DEFAULT 1.0,
            total_pulls  INT         NOT NULL DEFAULT 0,
            total_reward REAL        NOT NULL DEFAULT 0.0,
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (skill_id, agent_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_bandit_arms_agent ON skill_bandit_arms (agent_id)")

    # Add rl_mode column to agents — NULL = trigger matching (default), "bandit" = Thompson Sampling
    op.execute(
        """
        ALTER TABLE agents
          ADD COLUMN IF NOT EXISTS rl_mode TEXT DEFAULT NULL
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS rl_mode")
    op.execute("DROP INDEX IF EXISTS idx_bandit_arms_agent")
    op.execute("DROP TABLE IF EXISTS skill_bandit_arms")
