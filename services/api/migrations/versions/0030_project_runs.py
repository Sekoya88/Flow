"""project_runs table — run history for research projects

Revision ID: 0030
Revises: 0029
Create Date: 2026-05-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0030"
down_revision: str | Sequence[str] | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_runs (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id        UUID NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
            papers_processed  INT NOT NULL DEFAULT 0,
            kg_nodes_before   INT NOT NULL DEFAULT 0,
            kg_nodes_after    INT NOT NULL DEFAULT 0,
            status            VARCHAR(20) NOT NULL DEFAULT 'completed',
            error_message     TEXT,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_runs_project ON project_runs (project_id, created_at DESC);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS project_runs;")
