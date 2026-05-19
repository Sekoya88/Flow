"""Add ref_id/ref_type columns and entity node_types to kg_nodes.

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-14
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old node_type CHECK, add new one with entity types
    op.execute("ALTER TABLE kg_nodes DROP CONSTRAINT IF EXISTS kg_nodes_node_type_check")
    op.execute("""
        ALTER TABLE kg_nodes ADD CONSTRAINT kg_nodes_node_type_check
        CHECK (node_type IN (
            'note','concept','topic','query','trace','skill','tool_call','prompt','metacog',
            'agent','genome_version','system_prompt','execution','sub_agent'
        ))
    """)

    # Add ref_id / ref_type columns for entity → node linkage
    op.execute("ALTER TABLE kg_nodes ADD COLUMN IF NOT EXISTS ref_id TEXT")
    op.execute("ALTER TABLE kg_nodes ADD COLUMN IF NOT EXISTS ref_type TEXT")

    # Conditional unique index: entity nodes are unique by (workspace_id, ref_type, ref_id)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_kg_nodes_entity
        ON kg_nodes (workspace_id, ref_type, ref_id)
        WHERE ref_id IS NOT NULL
    """)


def downgrade() -> None:
    # Note: this will fail if any rows contain the new entity node_types.
    # Delete or migrate those rows before downgrading.
    op.execute("DROP INDEX IF EXISTS idx_kg_nodes_entity")
    op.execute("ALTER TABLE kg_nodes DROP COLUMN IF EXISTS ref_id")
    op.execute("ALTER TABLE kg_nodes DROP COLUMN IF EXISTS ref_type")
    op.execute("ALTER TABLE kg_nodes DROP CONSTRAINT IF EXISTS kg_nodes_node_type_check")
    op.execute("""
        ALTER TABLE kg_nodes ADD CONSTRAINT kg_nodes_node_type_check
        CHECK (node_type IN ('note','concept','topic','query','trace','skill','tool_call','prompt','metacog'))
    """)
