"""self_harness — held-in/held-out golden split + self-harness edit log

Adds the two pieces the Self-Harness loop needs that don't already exist:
  1. golden_items.split — partitions each golden set into a held-in split (shown
     to the weakness miner / proposer) and a held-out split (only the validation
     gate sees it). Backfilled deterministically by a stable hash of the item id.
  2. self_harness_edits — one row per candidate edit evaluated in a round, with
     the measured held-in/held-out deltas and the accept/reject decision. Satisfies
     the paper's "rejected candidates remain logged" and makes the harness lineage
     auditable.

Revision ID: 0038
Revises: 0037
Create Date: 2026-06-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0038"
down_revision: str | Sequence[str] | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Held-in / held-out split on golden items.
    op.execute("ALTER TABLE golden_items ADD COLUMN IF NOT EXISTS split TEXT")
    # Deterministic ~50/50 partition by stable hash of the item id. Cast to bigint
    # before the bitwise AND so INT_MIN from hashtext() can't overflow.
    op.execute(
        """
        UPDATE golden_items
        SET split = CASE WHEN (hashtext(id::text)::bigint & 1) = 0
                         THEN 'held_in' ELSE 'held_out' END
        WHERE split IS NULL
        """
    )

    # 2. Per-round audit log of every candidate edit (accepted or rejected).
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS self_harness_edits (
            id             UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            round_id       UUID NOT NULL,
            agent_id       UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            workspace_id   UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            surface        TEXT NOT NULL,
            mutation_type  TEXT NOT NULL,
            target         TEXT,
            payload        JSONB NOT NULL DEFAULT '{}'::jsonb,
            delta_in       FLOAT,
            delta_ho       FLOAT,
            accepted       BOOLEAN NOT NULL DEFAULT false,
            rationale      TEXT,
            source_pattern TEXT,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_self_harness_edits_agent ON self_harness_edits (agent_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_self_harness_edits_round ON self_harness_edits (round_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS self_harness_edits")
    op.execute("ALTER TABLE golden_items DROP COLUMN IF EXISTS split")
