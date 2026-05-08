"""add genome versioning to agent_versions and ab_tests

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add status and trigger columns with CHECK constraints to agent_versions
    op.execute("""
        ALTER TABLE agent_versions
            ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active'
                CONSTRAINT av_status_check CHECK (status IN ('candidate', 'active', 'archived')),
            ADD COLUMN IF NOT EXISTS trigger TEXT NOT NULL DEFAULT 'manual'
                CONSTRAINT av_trigger_check CHECK (trigger IN ('manual', 'config_patch', 'skill_created', 'eval_pass')),
            ADD COLUMN IF NOT EXISTS avg_score FLOAT,
            ADD COLUMN IF NOT EXISTS pass_rate FLOAT,
            ADD COLUMN IF NOT EXISTS proposal_id UUID REFERENCES proposals(id) ON DELETE SET NULL
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_versions_active
            ON agent_versions (agent_id, status, created_at DESC)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_versions_proposal
            ON agent_versions (proposal_id) WHERE proposal_id IS NOT NULL
    """)

    # Add version FK columns to ab_tests
    op.execute("""
        ALTER TABLE ab_tests
            ADD COLUMN IF NOT EXISTS version_a_id UUID REFERENCES agent_versions(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS version_b_id UUID REFERENCES agent_versions(id) ON DELETE SET NULL
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE ab_tests DROP COLUMN IF EXISTS version_b_id")
    op.execute("ALTER TABLE ab_tests DROP COLUMN IF EXISTS version_a_id")

    op.execute("DROP INDEX IF EXISTS idx_agent_versions_proposal")
    op.execute("DROP INDEX IF EXISTS idx_agent_versions_active")

    op.execute("ALTER TABLE agent_versions DROP COLUMN IF EXISTS proposal_id")
    op.execute("ALTER TABLE agent_versions DROP COLUMN IF EXISTS pass_rate")
    op.execute("ALTER TABLE agent_versions DROP COLUMN IF EXISTS avg_score")
    op.execute("ALTER TABLE agent_versions DROP COLUMN IF EXISTS trigger")
    op.execute("ALTER TABLE agent_versions DROP COLUMN IF EXISTS status")
