"""create agent_schedules table

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-11
"""
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_schedules (
            id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            agent_id        UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            cron_expr       TEXT NOT NULL DEFAULT '0 8 * * *',
            prompt_template TEXT NOT NULL DEFAULT '',
            delivery_type   TEXT NOT NULL DEFAULT 'none',
            delivery_target TEXT,
            enabled         BOOLEAN NOT NULL DEFAULT true,
            last_run_at     TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_schedules_workspace
            ON agent_schedules (workspace_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_schedules_enabled
            ON agent_schedules (enabled) WHERE enabled = true
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_schedules")
