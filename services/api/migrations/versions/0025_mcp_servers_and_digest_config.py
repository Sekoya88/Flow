"""MCP servers, tool assignments, and research digest config.

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-22
"""

from alembic import op

revision: str = "0025"
down_revision: str = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mcp_servers (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            url         TEXT NOT NULL,
            transport   TEXT NOT NULL DEFAULT 'sse',
            active      BOOLEAN NOT NULL DEFAULT true,
            metadata    JSONB NOT NULL DEFAULT '{}',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_mcp_servers_workspace ON mcp_servers (workspace_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mcp_server_tool_assignments (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            mcp_server_id UUID NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE,
            agent_id     UUID REFERENCES agents(id) ON DELETE CASCADE,
            tool_name    TEXT NOT NULL,
            enabled      BOOLEAN NOT NULL DEFAULT true
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_mcp_tool_assignments_server
        ON mcp_server_tool_assignments (mcp_server_id)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_digest_config (
            id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id             UUID NOT NULL UNIQUE REFERENCES workspaces(id) ON DELETE CASCADE,
            enabled                  BOOLEAN NOT NULL DEFAULT false,
            schedule_hour            INTEGER NOT NULL DEFAULT 8,
            min_relevance_score      FLOAT NOT NULL DEFAULT 0.5,
            arxiv_categories         TEXT[] NOT NULL DEFAULT ARRAY['cs.AI','cs.LG','cs.CL'],
            custom_sources           TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
            obsidian_mode            TEXT NOT NULL DEFAULT 'filesystem',
            obsidian_vault_path      TEXT,
            obsidian_api_url         TEXT,
            obsidian_api_key_encrypted TEXT,
            obsidian_cloud_bucket    TEXT,
            created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at               TIMESTAMPTZ
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS digest_papers (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id     UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            title            TEXT NOT NULL,
            abstract         TEXT,
            source_url       TEXT,
            arxiv_id         TEXT,
            authors          TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
            categories       TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
            relevance_score  FLOAT NOT NULL DEFAULT 0.0,
            tldr             TEXT,
            key_insights     TEXT,
            summary_md       TEXT,
            flow_knowledge_id UUID,
            obsidian_path    TEXT,
            status           TEXT NOT NULL DEFAULT 'unread',
            published_at     TIMESTAMPTZ,
            digested_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_digest_papers_workspace
        ON digest_papers (workspace_id, digested_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS digest_papers")
    op.execute("DROP TABLE IF EXISTS workspace_digest_config")
    op.execute("DROP TABLE IF EXISTS mcp_server_tool_assignments")
    op.execute("DROP TABLE IF EXISTS mcp_servers")
