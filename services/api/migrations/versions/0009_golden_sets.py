"""create golden_sets evaluation framework

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS golden_sets (
            id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            description TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS golden_items (
            id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            set_id          UUID NOT NULL REFERENCES golden_sets(id) ON DELETE CASCADE,
            input_text      TEXT NOT NULL,
            expected_output TEXT NOT NULL,
            scoring_criteria TEXT,
            metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS golden_results (
            id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            item_id             UUID NOT NULL REFERENCES golden_items(id) ON DELETE CASCADE,
            agent_id            UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            agent_version_label TEXT,
            actual_output       TEXT,
            score               FLOAT,
            grading_rationale   TEXT,
            execution_id        UUID,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS ab_tests (
            id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            golden_set_id   UUID NOT NULL REFERENCES golden_sets(id) ON DELETE CASCADE,
            agent_a_id      UUID NOT NULL REFERENCES agents(id),
            agent_a_version TEXT,
            agent_b_id      UUID NOT NULL REFERENCES agents(id),
            agent_b_version TEXT,
            status          TEXT NOT NULL DEFAULT 'pending',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS ab_test_results (
            id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            test_id         UUID NOT NULL REFERENCES ab_tests(id) ON DELETE CASCADE,
            golden_item_id  UUID NOT NULL REFERENCES golden_items(id) ON DELETE CASCADE,
            agent_label     TEXT NOT NULL,
            score           FLOAT,
            actual_output   TEXT,
            grading_rationale TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_golden_items_set ON golden_items (set_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_golden_results_item ON golden_results (item_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ab_test_results_test ON ab_test_results (test_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ab_test_results")
    op.execute("DROP TABLE IF EXISTS ab_tests")
    op.execute("DROP TABLE IF EXISTS golden_results")
    op.execute("DROP TABLE IF EXISTS golden_items")
    op.execute("DROP TABLE IF EXISTS golden_sets")
