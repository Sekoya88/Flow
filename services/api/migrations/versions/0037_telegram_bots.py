"""telegram_bots — per-workspace Telegram bot registrations

Each row ties a Telegram bot token to a workspace + agent.
Inbound messages from Telegram are routed to that agent for execution.

Revision ID: 0037
Revises: 0036
Create Date: 2026-06-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0037"
down_revision: str | Sequence[str] | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE telegram_bots (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            agent_id        UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            user_id         UUID NOT NULL,
            bot_token       TEXT NOT NULL,
            bot_username    TEXT,
            webhook_secret  TEXT NOT NULL DEFAULT gen_random_uuid()::text,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX ON telegram_bots(workspace_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS telegram_bots;")
