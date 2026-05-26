"""research_projects table for long-running accumulation jobs

Revision ID: 0029
Revises: 0028
Create Date: 2026-05-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0029"
down_revision: str | Sequence[str] | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS research_projects (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id     UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            name             TEXT NOT NULL,
            goal             TEXT NOT NULL DEFAULT '',
            arxiv_categories TEXT[] NOT NULL DEFAULT '{}',
            source_urls      TEXT[] NOT NULL DEFAULT '{}',
            cadence_cron     TEXT NOT NULL DEFAULT '0 9 * * 1',
            kg_namespace     TEXT NOT NULL DEFAULT '',
            enabled          BOOLEAN NOT NULL DEFAULT true,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_run_at      TIMESTAMPTZ
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_research_projects_ws ON research_projects (workspace_id);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS research_projects;")
