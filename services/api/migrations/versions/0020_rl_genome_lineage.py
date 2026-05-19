"""RL genome lineage — parent_id, generation, mutation_type, reward_signal, metacog_snapshot.

Also creates rl_episodes table for tracking reward signals per evolution cycle.

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-19
"""

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Genome lineage tracking on agent_versions
    op.execute(
        """
        ALTER TABLE agent_versions
          ADD COLUMN IF NOT EXISTS parent_id UUID REFERENCES agent_versions(id) ON DELETE SET NULL,
          ADD COLUMN IF NOT EXISTS generation INT NOT NULL DEFAULT 0,
          ADD COLUMN IF NOT EXISTS mutation_type TEXT,
          ADD COLUMN IF NOT EXISTS reward_signal REAL,
          ADD COLUMN IF NOT EXISTS metacog_snapshot JSONB
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_av_parent ON agent_versions (parent_id) WHERE parent_id IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_av_generation ON agent_versions (agent_id, generation DESC)")

    # RL episodes — one row per evolution cycle attempt
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rl_episodes (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_id     UUID        NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            workspace_id UUID        NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            parent_genome_id UUID    REFERENCES agent_versions(id) ON DELETE SET NULL,
            candidate_genome_id UUID REFERENCES agent_versions(id) ON DELETE SET NULL,
            mutation_type TEXT,
            reward_before REAL,
            reward_after  REAL,
            reward_delta  REAL,
            promoted      BOOLEAN NOT NULL DEFAULT FALSE,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_rl_episodes_agent ON rl_episodes (agent_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_rl_episodes_agent")
    op.execute("DROP TABLE IF EXISTS rl_episodes")
    op.execute("DROP INDEX IF EXISTS idx_av_generation")
    op.execute("DROP INDEX IF EXISTS idx_av_parent")
    op.execute("ALTER TABLE agent_versions DROP COLUMN IF EXISTS metacog_snapshot")
    op.execute("ALTER TABLE agent_versions DROP COLUMN IF EXISTS reward_signal")
    op.execute("ALTER TABLE agent_versions DROP COLUMN IF EXISTS mutation_type")
    op.execute("ALTER TABLE agent_versions DROP COLUMN IF EXISTS generation")
    op.execute("ALTER TABLE agent_versions DROP COLUMN IF EXISTS parent_id")
