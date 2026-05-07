"""create kg + agent_skills tables, add 'trace' node_type

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
    op.execute("""
        CREATE TABLE IF NOT EXISTS kg_nodes (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            label         TEXT NOT NULL,
            node_type     TEXT NOT NULL CHECK (node_type IN ('note','concept','topic','query','trace')),
            source_path   TEXT,
            content_hash  TEXT,
            summary       TEXT,
            embedding     vector(1536),
            metadata      JSONB NOT NULL DEFAULT '{}',
            cluster_id    INT,
            pagerank      FLOAT NOT NULL DEFAULT 0.0,
            pos_x         FLOAT NOT NULL DEFAULT 0.0,
            pos_y         FLOAT NOT NULL DEFAULT 0.0,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (workspace_id, label, node_type)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_kg_nodes_workspace_type ON kg_nodes (workspace_id, node_type);")
    op.execute("""
        CREATE TABLE IF NOT EXISTS kg_edges (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            source_id     UUID NOT NULL REFERENCES kg_nodes(id) ON DELETE CASCADE,
            target_id     UUID NOT NULL REFERENCES kg_nodes(id) ON DELETE CASCADE,
            edge_type     TEXT NOT NULL,
            weight        FLOAT NOT NULL DEFAULT 1.0,
            metadata      JSONB NOT NULL DEFAULT '{}',
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (source_id, target_id, edge_type)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_kg_edges_source ON kg_edges (workspace_id, source_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_kg_edges_target ON kg_edges (workspace_id, target_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_skills (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_id UUID NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
            workspace_id UUID NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            version INT NOT NULL DEFAULT 1,
            content_md TEXT NOT NULL,
            active BOOLEAN NOT NULL DEFAULT true,
            score REAL NOT NULL DEFAULT 1.0,
            use_count INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_skills_active ON agent_skills (agent_id, workspace_id, active);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_skills;")
    op.execute("DROP TABLE IF EXISTS kg_edges;")
    op.execute("DROP TABLE IF EXISTS kg_nodes;")
