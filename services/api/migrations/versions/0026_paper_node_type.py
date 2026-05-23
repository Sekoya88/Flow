"""Add paper node_type to kg_nodes for research digest integration.

Revision ID: 0026
Revises: 0025
Create Date: 2026-05-22
"""

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE kg_nodes DROP CONSTRAINT IF EXISTS kg_nodes_node_type_check")
    op.execute("""
        ALTER TABLE kg_nodes ADD CONSTRAINT kg_nodes_node_type_check
        CHECK (node_type IN (
            'note','concept','topic','query','trace','skill','tool_call','prompt','metacog',
            'agent','genome_version','system_prompt','execution','sub_agent','paper'
        ))
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE kg_nodes DROP CONSTRAINT IF EXISTS kg_nodes_node_type_check")
    op.execute("""
        ALTER TABLE kg_nodes ADD CONSTRAINT kg_nodes_node_type_check
        CHECK (node_type IN (
            'note','concept','topic','query','trace','skill','tool_call','prompt','metacog',
            'agent','genome_version','system_prompt','execution','sub_agent'
        ))
    """)
