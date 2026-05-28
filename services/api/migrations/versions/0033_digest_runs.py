"""Add digest_runs table, digest_run_id FK on digest_papers, and obsidian_vault_path on workspaces

Revision ID: 0033
Revises: 0032
Create Date: 2026-05-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0033"
down_revision: str | Sequence[str] | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS digest_runs (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            status       TEXT NOT NULL DEFAULT 'running',
            source       TEXT,
            paper_count  INT  NOT NULL DEFAULT 0,
            error        TEXT,
            started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS digest_runs_ws_idx
        ON digest_runs (workspace_id, started_at DESC);
    """)
    op.execute("""
        ALTER TABLE digest_papers
        ADD COLUMN IF NOT EXISTS digest_run_id UUID REFERENCES digest_runs(id) ON DELETE SET NULL;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS digest_papers_run_idx
        ON digest_papers (digest_run_id);
    """)
    op.execute("""
        ALTER TABLE workspaces
        ADD COLUMN IF NOT EXISTS obsidian_vault_path TEXT;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS digest_papers_run_idx;")
    op.execute("ALTER TABLE digest_papers DROP COLUMN IF EXISTS digest_run_id;")
    op.execute("DROP INDEX IF EXISTS digest_runs_ws_idx;")
    op.execute("DROP TABLE IF EXISTS digest_runs;")
    op.execute("ALTER TABLE workspaces DROP COLUMN IF EXISTS obsidian_vault_path;")
