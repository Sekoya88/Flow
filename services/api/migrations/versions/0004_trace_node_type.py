"""add_trace_node_type — extend kg_nodes CHECK to include 'trace'

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE kg_nodes DROP CONSTRAINT IF EXISTS kg_nodes_node_type_check")
    op.execute(
        "ALTER TABLE kg_nodes ADD CONSTRAINT kg_nodes_node_type_check "
        "CHECK (node_type IN ('note','concept','topic','query','trace'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE kg_nodes DROP CONSTRAINT IF EXISTS kg_nodes_node_type_check")
    op.execute(
        "ALTER TABLE kg_nodes ADD CONSTRAINT kg_nodes_node_type_check "
        "CHECK (node_type IN ('note','concept','topic','query'))"
    )
