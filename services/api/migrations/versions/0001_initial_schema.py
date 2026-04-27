"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-04-27 16:11:26.240779

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workspaces (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_members (
            workspace_id UUID NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('admin', 'editor', 'viewer')),
            PRIMARY KEY (workspace_id, user_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            template TEXT NOT NULL DEFAULT 'deer_flow',
            config JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS executions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_id UUID NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
            workspace_id UUID NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
            error TEXT,
            user_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS execution_events (
            id BIGSERIAL PRIMARY KEY,
            execution_id UUID NOT NULL REFERENCES executions (id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS ix_execution_events_exec ON execution_events (execution_id, id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_sources (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id BIGSERIAL PRIMARY KEY,
            source_id UUID NOT NULL REFERENCES knowledge_sources (id) ON DELETE CASCADE,
            chunk_index INT NOT NULL,
            content TEXT NOT NULL,
            embedding vector(1536)
        )
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_source ON knowledge_chunks (source_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            key TEXT NOT NULL,
            value JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, key)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_memories (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
            agent_id UUID NOT NULL REFERENCES agents (id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            embedding vector(1536),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agent_memories_lookup ON agent_memories (workspace_id, agent_id, user_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS execution_feedback (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            execution_id UUID NOT NULL REFERENCES executions (id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            score REAL NOT NULL CHECK (score >= 0 AND score <= 1),
            comment TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (execution_id, user_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS proposals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_proposals_workspace_status ON proposals (workspace_id, status)"
    )

    # Idempotent column patches (originally in apply_schema post-DDL block)
    op.execute(
        """
        DO $$ BEGIN
            ALTER TABLE knowledge_sources ADD COLUMN ingest_status TEXT NOT NULL DEFAULT 'indexed';
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
        """
    )

    op.execute(
        """
        DO $$ BEGIN
            ALTER TABLE knowledge_sources ADD COLUMN ingest_error TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
        """
    )

    op.execute(
        """
        DO $$ BEGIN
            ALTER TABLE proposals ADD COLUMN execution_id UUID
                REFERENCES executions (id) ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
        """
    )


def downgrade() -> None:
    pass  # no downgrade from initial migration
