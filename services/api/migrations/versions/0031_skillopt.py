"""skillopt reflact integration — training runs, patches, and epochs tables

Revision ID: 0031
Revises: 0030
Create Date: 2026-05-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0031"
down_revision: str | Sequence[str] | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS skill_training_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            skill_id UUID NOT NULL REFERENCES agent_skills(id) ON DELETE CASCADE,
            agent_id UUID NOT NULL,
            workspace_id UUID NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            epoch INT NOT NULL DEFAULT 0,
            edit_budget INT NOT NULL DEFAULT 5,
            edits_used INT NOT NULL DEFAULT 0,
            baseline_score REAL,
            best_score REAL,
            accepted BOOLEAN,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS skill_raw_patches (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID NOT NULL REFERENCES skill_training_runs(id) ON DELETE CASCADE,
            epoch INT NOT NULL DEFAULT 0,
            patch_json JSONB NOT NULL,
            applied BOOLEAN NOT NULL DEFAULT false,
            rejected BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS skill_training_epochs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id UUID NOT NULL REFERENCES skill_training_runs(id) ON DELETE CASCADE,
            epoch INT NOT NULL,
            candidate_skill_id UUID REFERENCES agent_skills(id) ON DELETE SET NULL,
            eval_score REAL NOT NULL,
            baseline_score REAL NOT NULL,
            accepted BOOLEAN NOT NULL,
            patch_count INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_skill_training_runs_skill ON skill_training_runs (skill_id, created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_skill_raw_patches_run ON skill_raw_patches (run_id, epoch);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_skill_training_epochs_run ON skill_training_epochs (run_id, epoch);")
    op.execute("""
        ALTER TABLE agent_skills
            ADD COLUMN IF NOT EXISTS training_mode TEXT DEFAULT NULL,
            ADD COLUMN IF NOT EXISTS last_training_run_id UUID REFERENCES skill_training_runs(id) ON DELETE SET NULL;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE agent_skills DROP COLUMN IF EXISTS last_training_run_id;")
    op.execute("ALTER TABLE agent_skills DROP COLUMN IF EXISTS training_mode;")
    op.execute("DROP TABLE IF EXISTS skill_training_epochs;")
    op.execute("DROP TABLE IF EXISTS skill_raw_patches;")
    op.execute("DROP TABLE IF EXISTS skill_training_runs;")
