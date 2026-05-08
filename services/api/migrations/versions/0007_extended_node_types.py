"""extend kg_nodes node_types for skills/tools/prompts/metacognition

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE kg_nodes DROP CONSTRAINT IF EXISTS kg_nodes_node_type_check")
    op.execute(
        "ALTER TABLE kg_nodes ADD CONSTRAINT kg_nodes_node_type_check "
        "CHECK (node_type IN ('note','concept','topic','query','trace','skill','tool_call','prompt','metacog'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE kg_nodes DROP CONSTRAINT IF EXISTS kg_nodes_node_type_check")
    op.execute(
        "ALTER TABLE kg_nodes ADD CONSTRAINT kg_nodes_node_type_check "
        "CHECK (node_type IN ('note','concept','topic','query','trace'))"
    )
