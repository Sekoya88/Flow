from __future__ import annotations

import json
from uuid import UUID

import asyncpg


def _vec_literal(values: list[float]) -> str:
    return "[" + ",".join(str(float(x)) for x in values) + "]"


class FlowRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_user(self, email: str, password_hash: str) -> UUID:
        row = await self._pool.fetchrow(
            "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
            email.lower().strip(),
            password_hash,
        )
        assert row is not None
        return row["id"]

    async def get_user_by_email(self, email: str) -> asyncpg.Record | None:
        return await self._pool.fetchrow(
            "SELECT id, email, password_hash, created_at FROM users WHERE email = $1",
            email.lower().strip(),
        )

    async def get_user(self, user_id: UUID) -> asyncpg.Record | None:
        return await self._pool.fetchrow(
            "SELECT id, email, created_at FROM users WHERE id = $1", user_id
        )

    async def create_workspace(self, name: str) -> UUID:
        row = await self._pool.fetchrow(
            "INSERT INTO workspaces (name) VALUES ($1) RETURNING id", name
        )
        assert row is not None
        return row["id"]

    async def add_workspace_member(self, workspace_id: UUID, user_id: UUID, role: str) -> None:
        await self._pool.execute(
            """
            INSERT INTO workspace_members (workspace_id, user_id, role)
            VALUES ($1, $2, $3)
            ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = EXCLUDED.role
            """,
            workspace_id,
            user_id,
            role,
        )

    async def list_workspaces_for_user(self, user_id: UUID) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            """
            SELECT w.id, w.name, w.created_at, m.role
            FROM workspaces w
            JOIN workspace_members m ON m.workspace_id = w.id
            WHERE m.user_id = $1
            ORDER BY w.created_at
            """,
            user_id,
        )

    async def create_agent(self, workspace_id: UUID, name: str, template: str, config: dict) -> UUID:
        row = await self._pool.fetchrow(
            """
            INSERT INTO agents (workspace_id, name, template, config)
            VALUES ($1, $2, $3, $4::jsonb) RETURNING id
            """,
            workspace_id,
            name,
            template,
            json.dumps(config),
        )
        assert row is not None
        return row["id"]

    async def list_agents(self, workspace_id: UUID) -> list[asyncpg.Record]:
        q = (
            "SELECT id, name, template, config, created_at FROM agents "
            "WHERE workspace_id = $1 ORDER BY created_at DESC"
        )
        return await self._pool.fetch(q, workspace_id)

    async def get_agent(self, agent_id: UUID, workspace_id: UUID) -> asyncpg.Record | None:
        q = (
            "SELECT id, workspace_id, name, template, config, created_at FROM agents "
            "WHERE id = $1 AND workspace_id = $2"
        )
        return await self._pool.fetchrow(q, agent_id, workspace_id)

    async def update_agent_config(self, agent_id: UUID, workspace_id: UUID, config: dict) -> bool:
        row = await self._pool.fetchrow(
            """
            UPDATE agents SET config = $3::jsonb
            WHERE id = $1 AND workspace_id = $2
            RETURNING id
            """,
            agent_id,
            workspace_id,
            json.dumps(config),
        )
        return row is not None

    async def update_agent_name(self, agent_id: UUID, workspace_id: UUID, name: str) -> bool:
        row = await self._pool.fetchrow(
            """
            UPDATE agents SET name = $3
            WHERE id = $1 AND workspace_id = $2
            RETURNING id
            """,
            agent_id,
            workspace_id,
            name.strip(),
        )
        return row is not None

    async def list_executions_for_workspace(
        self, workspace_id: UUID, *, limit: int = 40
    ) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            """
            SELECT e.id, e.agent_id, e.status, e.user_message, e.error, e.created_at, e.completed_at,
                   a.name AS agent_name, a.template AS agent_template
            FROM executions e
            JOIN agents a ON a.id = e.agent_id
            WHERE e.workspace_id = $1
            ORDER BY e.created_at DESC
            LIMIT $2
            """,
            workspace_id,
            limit,
        )

    async def create_execution(
        self, agent_id: UUID, workspace_id: UUID, user_message: str
    ) -> UUID:
        row = await self._pool.fetchrow(
            """
            INSERT INTO executions (agent_id, workspace_id, status, user_message)
            VALUES ($1, $2, 'running', $3) RETURNING id
            """,
            agent_id,
            workspace_id,
            user_message,
        )
        assert row is not None
        return row["id"]

    async def get_execution_for_user(self, execution_id: UUID, user_id: UUID) -> asyncpg.Record | None:
        return await self._pool.fetchrow(
            """
            SELECT e.id, e.status, e.agent_id, e.workspace_id, e.user_message, e.created_at
            FROM executions e
            JOIN agents a ON a.id = e.agent_id
            JOIN workspace_members m ON m.workspace_id = a.workspace_id
            WHERE e.id = $1 AND m.user_id = $2
            """,
            execution_id,
            user_id,
        )

    async def complete_execution(self, execution_id: UUID, status: str, error: str | None) -> None:
        await self._pool.execute(
            """
            UPDATE executions
            SET status = $2, error = $3, completed_at = now()
            WHERE id = $1
            """,
            execution_id,
            status,
            error,
        )

    async def insert_event(self, execution_id: UUID, kind: str, payload: dict) -> None:
        await self._pool.execute(
            """
            INSERT INTO execution_events (execution_id, kind, payload)
            VALUES ($1, $2, $3::jsonb)
            """,
            execution_id,
            kind,
            json.dumps(payload),
        )

    async def get_execution_events(
        self, execution_id: UUID, after_id: int = 0
    ) -> list[dict]:
        rows = await self._pool.fetch(
            """
            SELECT id, kind, payload
            FROM execution_events
            WHERE execution_id = $1 AND id > $2
            ORDER BY id
            """,
            execution_id,
            after_id,
        )
        return [{"id": r["id"], "kind": r["kind"], "payload": r["payload"]} for r in rows]

    async def list_events(self, execution_id: UUID) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            "SELECT id, kind, payload, created_at FROM execution_events WHERE execution_id = $1 ORDER BY id ASC",
            execution_id,
        )

    async def insert_knowledge_source(
        self, workspace_id: UUID, title: str, body: str, *, ingest_status: str = "processing"
    ) -> UUID:
        row = await self._pool.fetchrow(
            """
            INSERT INTO knowledge_sources (workspace_id, title, body, ingest_status, ingest_error)
            VALUES ($1, $2, $3, $4, NULL) RETURNING id
            """,
            workspace_id,
            title,
            body,
            ingest_status,
        )
        assert row is not None
        return row["id"]

    async def set_knowledge_ingest(
        self, source_id: UUID, status: str, error: str | None = None
    ) -> None:
        await self._pool.execute(
            """
            UPDATE knowledge_sources
            SET ingest_status = $2, ingest_error = $3
            WHERE id = $1
            """,
            source_id,
            status,
            error,
        )

    async def list_knowledge_sources(self, workspace_id: UUID) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            """
            SELECT s.id, s.title, s.created_at, s.ingest_status, s.ingest_error,
                   (SELECT COUNT(*)::int FROM knowledge_chunks c WHERE c.source_id = s.id) AS chunk_count
            FROM knowledge_sources s
            WHERE s.workspace_id = $1
            ORDER BY s.created_at DESC
            """,
            workspace_id,
        )

    async def list_chunks_for_source(self, source_id: UUID, workspace_id: UUID) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            """
            SELECT kc.id, kc.chunk_index, kc.content
            FROM knowledge_chunks kc
            JOIN knowledge_sources ks ON ks.id = kc.source_id
            WHERE kc.source_id = $1 AND ks.workspace_id = $2
            ORDER BY kc.chunk_index
            """,
            source_id,
            workspace_id,
        )

    async def insert_chunk(
        self, source_id: UUID, chunk_index: int, content: str, embedding: list[float]
    ) -> int:
        row = await self._pool.fetchrow(
            """
            INSERT INTO knowledge_chunks (source_id, chunk_index, content, embedding)
            VALUES ($1, $2, $3, $4::vector)
            RETURNING id
            """,
            source_id,
            chunk_index,
            content,
            _vec_literal(embedding),
        )
        assert row is not None
        return int(row["id"])

    async def search_knowledge(
        self, workspace_id: UUID, embedding: list[float], limit: int = 5
    ) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            """
            SELECT kc.id, kc.chunk_index, kc.content,
                   ks.id AS source_id, ks.title AS source_title,
                   kc.embedding <=> $1::vector AS dist
            FROM knowledge_chunks kc
            JOIN knowledge_sources ks ON ks.id = kc.source_id
            WHERE ks.workspace_id = $2
            ORDER BY kc.embedding <=> $1::vector
            LIMIT $3
            """,
            _vec_literal(embedding),
            workspace_id,
            limit,
        )

    async def upsert_preference(self, user_id: UUID, key: str, value: dict) -> None:
        await self._pool.execute(
            """
            INSERT INTO user_preferences (user_id, key, value)
            VALUES ($1, $2, $3::jsonb)
            ON CONFLICT (user_id, key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
            """,
            user_id,
            key,
            json.dumps(value),
        )

    async def get_preferences(self, user_id: UUID) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            "SELECT key, value, updated_at FROM user_preferences WHERE user_id = $1 ORDER BY key",
            user_id,
        )

    async def insert_memory(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        user_id: UUID,
        content: str,
        embedding: list[float] | None,
    ) -> UUID:
        if embedding is None:
            row = await self._pool.fetchrow(
                """
                INSERT INTO agent_memories (workspace_id, agent_id, user_id, content, embedding)
                VALUES ($1, $2, $3, $4, NULL) RETURNING id
                """,
                workspace_id,
                agent_id,
                user_id,
                content,
            )
        else:
            row = await self._pool.fetchrow(
                """
                INSERT INTO agent_memories (workspace_id, agent_id, user_id, content, embedding)
                VALUES ($1, $2, $3, $4, $5::vector) RETURNING id
                """,
                workspace_id,
                agent_id,
                user_id,
                content,
                _vec_literal(embedding),
            )
        assert row is not None
        return row["id"]

    async def search_memories(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        user_id: UUID,
        embedding: list[float],
        limit: int = 5,
    ) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            """
            SELECT content, embedding <=> $1::vector AS dist
            FROM agent_memories
            WHERE workspace_id = $2 AND agent_id = $3 AND user_id = $4 AND embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $5
            """,
            _vec_literal(embedding),
            workspace_id,
            agent_id,
            user_id,
            limit,
        )

    async def upsert_feedback(
        self, execution_id: UUID, user_id: UUID, score: float, comment: str | None
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO execution_feedback (execution_id, user_id, score, comment)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (execution_id, user_id) DO UPDATE SET score = EXCLUDED.score, comment = EXCLUDED.comment
            """,
            execution_id,
            user_id,
            score,
            comment,
        )

    async def create_proposal(
        self,
        workspace_id: UUID,
        user_id: UUID,
        title: str,
        body: str,
        *,
        execution_id: UUID | None = None,
    ) -> UUID:
        row = await self._pool.fetchrow(
            """
            INSERT INTO proposals (workspace_id, user_id, title, body, status, execution_id)
            VALUES ($1, $2, $3, $4, 'pending', $5) RETURNING id
            """,
            workspace_id,
            user_id,
            title,
            body,
            execution_id,
        )
        assert row is not None
        return row["id"]

    async def list_proposals(self, workspace_id: UUID, status: str | None = None) -> list[asyncpg.Record]:
        cols = "id, title, body, status, created_at, execution_id"
        if status:
            q = (
                f"SELECT {cols} FROM proposals "
                "WHERE workspace_id = $1 AND status = $2 ORDER BY created_at DESC"
            )
            return await self._pool.fetch(q, workspace_id, status)
        q = f"SELECT {cols} FROM proposals WHERE workspace_id = $1 ORDER BY created_at DESC"
        return await self._pool.fetch(q, workspace_id)

    async def dashboard_counts(self, user_id: UUID) -> dict[str, int]:
        ws_ids = await self._pool.fetch("SELECT workspace_id FROM workspace_members WHERE user_id = $1", user_id)
        if not ws_ids:
            return {"agents": 0, "executions": 0, "knowledge": 0, "pending_proposals": 0}
        ids = [r["workspace_id"] for r in ws_ids]
        agents = await self._pool.fetchval(
            "SELECT COUNT(*) FROM agents WHERE workspace_id = ANY($1::uuid[])", ids
        )
        executions = await self._pool.fetchval(
            """
            SELECT COUNT(*) FROM executions e
            JOIN agents a ON a.id = e.agent_id
            WHERE a.workspace_id = ANY($1::uuid[])
            """,
            ids,
        )
        knowledge = await self._pool.fetchval(
            "SELECT COUNT(*) FROM knowledge_sources WHERE workspace_id = ANY($1::uuid[])", ids
        )
        proposals = await self._pool.fetchval(
            """
            SELECT COUNT(*) FROM proposals
            WHERE workspace_id = ANY($1::uuid[]) AND status = 'pending'
            """,
            ids,
        )
        return {
            "agents": int(agents or 0),
            "executions": int(executions or 0),
            "knowledge": int(knowledge or 0),
            "pending_proposals": int(proposals or 0),
        }

    async def set_proposal_status(self, proposal_id: UUID, workspace_id: UUID, status: str) -> bool:
        row = await self._pool.fetchrow(
            """
            UPDATE proposals SET status = $3
            WHERE id = $1 AND workspace_id = $2
            RETURNING id
            """,
            proposal_id,
            workspace_id,
            status,
        )
        return row is not None

    # ------------------------------------------------------------------
    # Episodic memory (per-execution summaries)
    # ------------------------------------------------------------------

    async def insert_episodic_memory(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        user_id: UUID,
        content: str,
        embedding: list[float] | None,
        execution_id: UUID | None = None,
    ) -> UUID:
        vec = _vec_literal(embedding) if embedding is not None else None
        row = await self._pool.fetchrow(
            """
            INSERT INTO episodic_memories
                (workspace_id, agent_id, user_id, execution_id, content, embedding)
            VALUES ($1, $2, $3, $4, $5, $6::vector)
            RETURNING id
            """,
            workspace_id,
            agent_id,
            user_id,
            execution_id,
            content,
            vec,
        )
        assert row is not None
        return row["id"]

    async def list_episodic_memories(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        user_id: UUID,
        limit: int = 20,
    ) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            """
            SELECT id, content, execution_id, created_at
            FROM episodic_memories
            WHERE workspace_id = $1 AND agent_id = $2 AND user_id = $3
            ORDER BY created_at DESC
            LIMIT $4
            """,
            workspace_id,
            agent_id,
            user_id,
            limit,
        )

    async def list_semantic_memories(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        user_id: UUID,
        limit: int = 20,
    ) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            """
            SELECT id, content, created_at
            FROM agent_memories
            WHERE workspace_id = $1 AND agent_id = $2 AND user_id = $3
            ORDER BY created_at DESC
            LIMIT $4
            """,
            workspace_id,
            agent_id,
            user_id,
            limit,
        )

    # ------------------------------------------------------------------
    # Reasoning patterns (ReasoningBank)
    # ------------------------------------------------------------------

    async def insert_reasoning_pattern(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        problem_summary: str,
        solution_steps: str,
        embedding: list[float] | None,
        score: float = 1.0,
    ) -> UUID:
        vec = _vec_literal(embedding) if embedding is not None else None
        row = await self._pool.fetchrow(
            """
            INSERT INTO reasoning_patterns
                (workspace_id, agent_id, problem_summary, solution_steps, embedding, score)
            VALUES ($1, $2, $3, $4, $5::vector, $6)
            RETURNING id
            """,
            workspace_id,
            agent_id,
            problem_summary,
            solution_steps,
            vec,
            score,
        )
        assert row is not None
        return row["id"]

    async def search_reasoning_patterns(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        embedding: list[float],
        limit: int = 3,
    ) -> list[asyncpg.Record]:
        vec = _vec_literal(embedding)
        return await self._pool.fetch(
            """
            SELECT id, problem_summary, solution_steps, score, use_count
            FROM reasoning_patterns
            WHERE workspace_id = $1 AND agent_id = $2 AND embedding IS NOT NULL
            ORDER BY embedding <=> $3::vector
            LIMIT $4
            """,
            workspace_id,
            agent_id,
            vec,
            limit,
        )

    async def increment_pattern_use(self, pattern_id: UUID) -> None:
        await self._pool.execute(
            "UPDATE reasoning_patterns SET use_count = use_count + 1 WHERE id = $1",
            pattern_id,
        )

    async def delete_episodic_memory(self, memory_id: UUID, workspace_id: UUID) -> bool:
        result = await self._pool.execute(
            "DELETE FROM episodic_memories WHERE id = $1 AND workspace_id = $2",
            memory_id,
            workspace_id,
        )
        return result == "DELETE 1"

    # ------------------------------------------------------------------
    # Agent negatives
    # ------------------------------------------------------------------

    async def insert_agent_negative(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        content: str,
        source: str = "feedback",
    ) -> UUID:
        row = await self._pool.fetchrow(
            """
            INSERT INTO agent_negatives (workspace_id, agent_id, content, source)
            VALUES ($1, $2, $3, $4) RETURNING id
            """,
            workspace_id,
            agent_id,
            content,
            source,
        )
        assert row is not None
        return row["id"]

    # ------------------------------------------------------------------
    # Agent schedules
    # ------------------------------------------------------------------

    async def create_agent_schedule(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        user_id: UUID,
        cron_expr: str,
        prompt_template: str,
        delivery_type: str = "none",
        delivery_target: str | None = None,
    ) -> UUID:
        row = await self._pool.fetchrow(
            """
            INSERT INTO agent_schedules
                (workspace_id, agent_id, user_id, cron_expr, prompt_template, delivery_type, delivery_target)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            workspace_id, agent_id, user_id, cron_expr, prompt_template, delivery_type, delivery_target,
        )
        assert row is not None
        return row["id"]

    async def list_agent_schedules(
        self,
        workspace_id: UUID,
        user_id: UUID,
    ) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            """
            SELECT s.*, a.name AS agent_name
            FROM agent_schedules s
            JOIN agents a ON a.id = s.agent_id
            WHERE s.workspace_id = $1 AND s.user_id = $2
            ORDER BY s.created_at DESC
            """,
            workspace_id, user_id,
        )

    async def list_enabled_schedules(self) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            "SELECT * FROM agent_schedules WHERE enabled = true"
        )

    async def update_schedule_enabled(self, schedule_id: UUID, enabled: bool) -> None:
        await self._pool.execute(
            "UPDATE agent_schedules SET enabled = $1 WHERE id = $2",
            enabled, schedule_id,
        )

    async def update_schedule_last_run(self, schedule_id: UUID) -> None:
        await self._pool.execute(
            "UPDATE agent_schedules SET last_run_at = now() WHERE id = $1",
            schedule_id,
        )

    async def delete_agent_schedule(self, schedule_id: UUID, workspace_id: UUID) -> bool:
        result = await self._pool.execute(
            "DELETE FROM agent_schedules WHERE id = $1 AND workspace_id = $2",
            schedule_id, workspace_id,
        )
        return result == "DELETE 1"

    async def list_agent_negatives(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        limit: int = 10,
    ) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            """
            SELECT id, content, source, created_at
            FROM agent_negatives
            WHERE workspace_id = $1 AND agent_id = $2
            ORDER BY created_at DESC
            LIMIT $3
            """,
            workspace_id,
            agent_id,
            limit,
        )
