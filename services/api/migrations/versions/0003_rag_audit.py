"""rag_audit — query trace + citations for agentic RAG

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_query_history (
            id BIGSERIAL PRIMARY KEY,
            execution_id UUID REFERENCES executions (id) ON DELETE SET NULL,
            workspace_id UUID NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
            query_original TEXT NOT NULL,
            query_rewritten TEXT,
            routing_decision TEXT,
            iteration_count INT NOT NULL DEFAULT 1,
            fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
            confidence_score DOUBLE PRECISION,
            latency_ms JSONB NOT NULL DEFAULT '{}'::jsonb,
            explanation JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_citations (
            id BIGSERIAL PRIMARY KEY,
            query_history_id BIGINT NOT NULL REFERENCES rag_query_history (id) ON DELETE CASCADE,
            chunk_id TEXT NOT NULL,
            source_url TEXT,
            source_title TEXT,
            page_number INT,
            excerpt TEXT,
            relevance_score DOUBLE PRECISION,
            used_in_answer BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_rag_query_history_execution ON rag_query_history (execution_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rag_query_history_workspace ON rag_query_history (workspace_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rag_query_history_created ON rag_query_history (created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rag_citations_query ON rag_citations (query_history_id)")
    op.execute(
        """
        CREATE OR REPLACE VIEW v_rag_explanation_full AS
        SELECT
            qh.id,
            qh.execution_id,
            qh.workspace_id,
            qh.query_original,
            qh.query_rewritten,
            qh.routing_decision,
            qh.iteration_count,
            qh.fallback_used,
            qh.confidence_score,
            qh.latency_ms,
            qh.explanation,
            qh.created_at,
            COALESCE(
                json_agg(
                    json_build_object(
                        'chunk_id', c.chunk_id,
                        'source_url', c.source_url,
                        'source_title', c.source_title,
                        'excerpt', c.excerpt,
                        'relevance_score', c.relevance_score,
                        'used_in_answer', c.used_in_answer
                    )
                ) FILTER (WHERE c.id IS NOT NULL),
                '[]'::json
            ) AS citations
        FROM rag_query_history qh
        LEFT JOIN rag_citations c ON c.query_history_id = qh.id
        GROUP BY qh.id
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_rag_explanation_full")
    op.execute("DROP TABLE IF EXISTS rag_citations")
    op.execute("DROP TABLE IF EXISTS rag_query_history")
