"""Add user_preferences table for typed facet-based preference system.

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-15
"""
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_preferences")
    op.execute("""
        CREATE TABLE user_preferences (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id         UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            user_id              UUID NOT NULL,
            agent_id             UUID REFERENCES agents(id) ON DELETE CASCADE,
            class                TEXT NOT NULL CHECK (class IN
                                     ('style','tooling','veto','goal','domain','channel')),
            value                TEXT NOT NULL,
            score                FLOAT NOT NULL DEFAULT 0.5,
            status               TEXT NOT NULL DEFAULT 'candidate'
                                     CHECK (status IN ('candidate','provisional','active')),
            pinned               BOOLEAN NOT NULL DEFAULT FALSE,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_reinforced_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            decay_half_life_days INT NOT NULL DEFAULT 30
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX idx_user_preferences_unique
        ON user_preferences (workspace_id, user_id,
                    COALESCE(agent_id, '00000000-0000-0000-0000-000000000000'::uuid),
                    class, value)
    """)
    op.execute("""
        CREATE INDEX idx_user_preferences_lookup
        ON user_preferences (workspace_id, user_id, agent_id, status)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_user_preferences_lookup")
    op.execute("DROP INDEX IF EXISTS idx_user_preferences_unique")
    op.execute("DROP TABLE IF EXISTS user_preferences")
