from __future__ import annotations

import json
from datetime import UTC
from uuid import UUID

import asyncpg

from flow.infrastructure.graph.entity_indexer import index_agent as _index_agent


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
        return await self._pool.fetchrow("SELECT id, email, created_at FROM users WHERE id = $1", user_id)

    async def create_workspace(self, name: str) -> UUID:
        row = await self._pool.fetchrow("INSERT INTO workspaces (name) VALUES ($1) RETURNING id", name)
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

    async def list_workspace_members(self, workspace_id: UUID) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            """
            SELECT u.id, u.email, wm.role
            FROM workspace_members wm
            JOIN users u ON u.id = wm.user_id
            WHERE wm.workspace_id = $1
            ORDER BY u.email
            """,
            workspace_id,
        )

    async def remove_workspace_member(self, workspace_id: UUID, user_id: UUID) -> None:
        await self._pool.execute(
            "DELETE FROM workspace_members WHERE workspace_id = $1 AND user_id = $2",
            workspace_id,
            user_id,
        )

    async def is_workspace_admin(self, workspace_id: UUID, user_id: UUID) -> bool:
        row = await self._pool.fetchrow(
            "SELECT role FROM workspace_members WHERE workspace_id = $1 AND user_id = $2",
            workspace_id,
            user_id,
        )
        return row is not None and row["role"] == "admin"

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
        agent_id = row["id"]
        try:
            await _index_agent(
                self._pool,
                workspace_id=workspace_id,
                agent_id=agent_id,
                name=name,
                template=template,
            )
        except Exception:
            pass
        return agent_id

    async def list_agents(self, workspace_id: UUID) -> list[asyncpg.Record]:
        q = "SELECT id, name, template, config, created_at FROM agents WHERE workspace_id = $1 ORDER BY created_at DESC"
        return await self._pool.fetch(q, workspace_id)

    async def get_agent(self, agent_id: UUID, workspace_id: UUID) -> asyncpg.Record | None:
        q = "SELECT id, workspace_id, name, template, config, created_at FROM agents WHERE id = $1 AND workspace_id = $2"
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

    async def list_executions_for_workspace(self, workspace_id: UUID, *, limit: int = 40) -> list[asyncpg.Record]:
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
        self,
        agent_id: UUID,
        workspace_id: UUID,
        user_message: str,
        *,
        thread_id: UUID | None = None,
    ) -> tuple[UUID, UUID]:
        """Create execution. Returns (execution_id, thread_id).

        When thread_id is None (single-turn), thread_id = the new execution_id.
        Passing a thread_id from a prior execution continues the same LangGraph
        checkpoint thread (multi-turn resume).
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO executions (agent_id, workspace_id, status, user_message, thread_id)
                    VALUES ($1, $2, 'running', $3, $4)
                    RETURNING id
                    """,
                    agent_id,
                    workspace_id,
                    user_message,
                    thread_id,
                )
                assert row is not None
                eid = row["id"]
                if thread_id is None:
                    await conn.execute(
                        "UPDATE executions SET thread_id = id WHERE id = $1",
                        eid,
                    )
                    return eid, eid
                return eid, thread_id

    async def get_thread_id(self, execution_id: UUID) -> UUID | None:
        row = await self._pool.fetchrow(
            "SELECT COALESCE(thread_id, id) AS thread_id FROM executions WHERE id = $1",
            execution_id,
        )
        return row["thread_id"] if row else None

    async def list_executions_for_user(self, user_id: UUID, *, limit: int = 60) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            """
            SELECT e.id, e.status, e.agent_id, e.workspace_id, COALESCE(e.thread_id, e.id) AS thread_id, e.user_message,
                   e.created_at, e.completed_at,
                   a.name AS agent_name, a.template AS agent_template,
                   (SELECT ee.payload->>'answer'
                    FROM execution_events ee
                    WHERE ee.execution_id = e.id AND ee.kind = 'final'
                    LIMIT 1) AS answer
            FROM executions e
            JOIN agents a ON a.id = e.agent_id
            JOIN workspace_members m ON m.workspace_id = e.workspace_id
            WHERE m.user_id = $1
            ORDER BY e.created_at DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )

    async def list_executions_in_thread(self, thread_id: UUID, user_id: UUID) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            """
            SELECT e.id, e.status, e.agent_id, e.workspace_id, COALESCE(e.thread_id, e.id) AS thread_id, e.user_message,
                   e.created_at, e.completed_at,
                   a.name AS agent_name, a.template AS agent_template,
                   (SELECT ee.payload->>'answer'
                    FROM execution_events ee
                    WHERE ee.execution_id = e.id AND ee.kind = 'final'
                    LIMIT 1) AS answer
            FROM executions e
            JOIN agents a ON a.id = e.agent_id
            JOIN workspace_members m ON m.workspace_id = e.workspace_id
            WHERE COALESCE(e.thread_id, e.id) = $1 AND m.user_id = $2
            ORDER BY e.created_at ASC
            """,
            thread_id,
            user_id,
        )

    async def get_execution_for_user(self, execution_id: UUID, user_id: UUID) -> asyncpg.Record | None:
        return await self._pool.fetchrow(
            """
            SELECT e.id, e.status, e.agent_id, e.workspace_id, COALESCE(e.thread_id, e.id) AS thread_id,
                   e.user_message, e.error, e.created_at, e.completed_at,
                   a.name AS agent_name, a.template AS agent_template,
                   (SELECT ee.payload->>'answer'
                    FROM execution_events ee
                    WHERE ee.execution_id = e.id AND ee.kind = 'final'
                    LIMIT 1) AS answer
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

    async def get_execution_events(self, execution_id: UUID, after_id: int = 0) -> list[dict]:
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

    async def insert_knowledge_source(self, workspace_id: UUID, title: str, body: str, *, ingest_status: str = "processing") -> UUID:
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

    async def set_knowledge_ingest(self, source_id: UUID, status: str, error: str | None = None) -> None:
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

    async def insert_chunk(self, source_id: UUID, chunk_index: int, content: str, embedding: list[float]) -> int:
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

    async def search_knowledge(self, workspace_id: UUID, embedding: list[float], limit: int = 5) -> list[asyncpg.Record]:
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

    # ── Typed user preferences ────────────────────────────────────────────

    async def load_profile(
        self,
        workspace_id: UUID,
        user_id: UUID,
        agent_id: UUID | None,
    ) -> list[asyncpg.Record]:
        """Load active/provisional preferences, delete decayed rows, return merged list."""
        rows = await self._pool.fetch(
            """
            SELECT id, class, value, score, status, pinned,
                   agent_id, last_reinforced_at, decay_half_life_days, created_at
            FROM user_preferences
            WHERE workspace_id = $1
              AND user_id = $2
              AND (agent_id = $3 OR agent_id IS NULL)
              AND status IN ('provisional', 'active')
            ORDER BY agent_id NULLS LAST, score DESC
            """,
            workspace_id,
            user_id,
            agent_id,
        )
        from datetime import datetime

        to_delete: list[asyncpg.Record] = []
        live: list[asyncpg.Record] = []
        for row in rows:
            pinned = row["pinned"]
            if pinned:
                live.append(row)
                continue
            lra = row["last_reinforced_at"]
            if lra.tzinfo is None:
                lra = lra.replace(tzinfo=UTC)
            days = (datetime.now(tz=UTC) - lra).total_seconds() / 86400
            eff = row["score"] * (0.5 ** (days / row["decay_half_life_days"]))
            if eff < 0.1:
                to_delete.append(row)
            else:
                live.append(row)

        if to_delete:
            ids = [r["id"] for r in to_delete]
            await self._pool.execute("DELETE FROM user_preferences WHERE id = ANY($1::uuid[])", ids)
        return live

    async def upsert_typed_preference(
        self,
        workspace_id: UUID,
        user_id: UUID,
        class_: str,
        value: str,
        agent_id: UUID | None = None,
        initial_status: str = "candidate",
    ) -> asyncpg.Record:
        """Upsert (reinforce) a preference; returns updated row."""
        row = await self._pool.fetchrow(
            """
            INSERT INTO user_preferences
                (workspace_id, user_id, agent_id, class, value, status)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (workspace_id, user_id,
                         COALESCE(agent_id, '00000000-0000-0000-0000-000000000000'::uuid),
                         class, value)
            DO UPDATE SET
                score = LEAST(1.0, user_preferences.score + 0.1),
                last_reinforced_at = NOW()
            RETURNING *
            """,
            workspace_id,
            user_id,
            agent_id,
            class_,
            value,
            initial_status,
        )
        return row

    async def apply_preference_graduation(
        self,
        pref_id: UUID,
        new_status: str,
    ) -> None:
        await self._pool.execute(
            "UPDATE user_preferences SET status = $1 WHERE id = $2",
            new_status,
            pref_id,
        )

    async def get_typed_preferences(
        self,
        workspace_id: UUID,
        user_id: UUID,
        agent_id: UUID | None = None,
        status: str | None = None,
        class_: str | None = None,
    ) -> tuple[list[asyncpg.Record], list[asyncpg.Record]]:
        """Return (global_rows, agent_specific_rows)."""
        conditions = ["workspace_id = $1", "user_id = $2"]
        params: list = [workspace_id, user_id]
        idx = 3

        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        if class_:
            conditions.append(f"class = ${idx}")
            params.append(class_)
            idx += 1

        where = " AND ".join(conditions)
        rows = await self._pool.fetch(
            f"""
            SELECT id, class, value, score, status, pinned,
                   agent_id, last_reinforced_at, decay_half_life_days, created_at
            FROM user_preferences
            WHERE {where}
            ORDER BY score DESC
            """,
            *params,
        )
        global_rows = [r for r in rows if r["agent_id"] is None]
        agent_rows = [r for r in rows if r["agent_id"] == agent_id] if agent_id else []
        return global_rows, agent_rows

    async def get_preference_by_id(self, pref_id: UUID, user_id: UUID) -> asyncpg.Record | None:
        return await self._pool.fetchrow(
            """
            SELECT id, class, value, score, status, pinned,
                   agent_id, workspace_id, last_reinforced_at, decay_half_life_days, created_at
            FROM user_preferences WHERE id = $1 AND user_id = $2
            """,
            pref_id,
            user_id,
        )

    async def patch_typed_preference(
        self,
        pref_id: UUID,
        user_id: UUID,
        action: str,
    ) -> asyncpg.Record | None:
        """Apply promote/pin/unpin/forget/veto actions. Returns updated row or None if deleted."""
        row = await self.get_preference_by_id(pref_id, user_id)
        if not row:
            return None

        if action == "promote":
            _ORDER = ["candidate", "provisional", "active"]
            current_idx = _ORDER.index(row["status"]) if row["status"] in _ORDER else -1
            if current_idx < len(_ORDER) - 1:
                next_status = _ORDER[current_idx + 1]
                return await self._pool.fetchrow(
                    "UPDATE user_preferences SET status = $1 WHERE id = $2 RETURNING *",
                    next_status,
                    pref_id,
                )
            return row

        if action == "pin":
            return await self._pool.fetchrow(
                "UPDATE user_preferences SET status = 'active', pinned = TRUE WHERE id = $1 RETURNING *",
                pref_id,
            )

        if action == "unpin":
            return await self._pool.fetchrow(
                "UPDATE user_preferences SET pinned = FALSE WHERE id = $1 RETURNING *",
                pref_id,
            )

        if action == "forget":
            await self._pool.execute("DELETE FROM user_preferences WHERE id = $1", pref_id)
            return None

        if action == "veto":
            # Delete original + insert veto entry to suppress future extraction
            await self._pool.execute("DELETE FROM user_preferences WHERE id = $1", pref_id)
            veto_row = await self.upsert_typed_preference(
                row["workspace_id"],
                user_id,
                "veto",
                row["value"],
                row["agent_id"],
                initial_status="active",
            )
            return veto_row

        return row

    async def delete_typed_preference(self, pref_id: UUID, user_id: UUID) -> bool:
        result = await self._pool.execute(
            "DELETE FROM user_preferences WHERE id = $1 AND user_id = $2",
            pref_id,
            user_id,
        )
        return result == "DELETE 1"

    async def get_onboarding_status(self, workspace_id: UUID, user_id: UUID) -> dict:
        count = await self._pool.fetchval(
            "SELECT COUNT(*) FROM user_preferences WHERE workspace_id = $1 AND user_id = $2",
            workspace_id,
            user_id,
        )
        return {"completed": int(count) > 0, "preference_count": int(count)}

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

    async def upsert_feedback(self, execution_id: UUID, user_id: UUID, score: float, comment: str | None) -> None:
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
        cols = "id, title, body, status, created_at, execution_id, auto_approved"
        if status:
            q = f"SELECT {cols} FROM proposals WHERE workspace_id = $1 AND status = $2 ORDER BY created_at DESC"
            return await self._pool.fetch(q, workspace_id, status)
        q = f"SELECT {cols} FROM proposals WHERE workspace_id = $1 ORDER BY created_at DESC"
        return await self._pool.fetch(q, workspace_id)

    async def dashboard_counts(self, user_id: UUID) -> dict:
        ws_ids = await self._pool.fetch("SELECT workspace_id FROM workspace_members WHERE user_id = $1", user_id)
        if not ws_ids:
            return {
                "counts": {"agents": 0, "executions": 0, "knowledge": 0, "pending_proposals": 0, "episodic_memories": 0, "active_schedules": 0},
                "recent_executions": [],
            }
        ids = [r["workspace_id"] for r in ws_ids]

        agents = await self._pool.fetchval("SELECT COUNT(*) FROM agents WHERE workspace_id = ANY($1::uuid[])", ids)
        executions = await self._pool.fetchval(
            """
            SELECT COUNT(*) FROM executions e
            JOIN agents a ON a.id = e.agent_id
            WHERE a.workspace_id = ANY($1::uuid[])
            """,
            ids,
        )
        knowledge = await self._pool.fetchval("SELECT COUNT(*) FROM knowledge_sources WHERE workspace_id = ANY($1::uuid[])", ids)
        proposals = await self._pool.fetchval(
            """
            SELECT COUNT(*) FROM proposals
            WHERE workspace_id = ANY($1::uuid[]) AND status = 'pending'
            """,
            ids,
        )
        episodic = await self._pool.fetchval("SELECT COUNT(*) FROM episodic_memories WHERE workspace_id = ANY($1::uuid[])", ids)
        schedules = await self._pool.fetchval("SELECT COUNT(*) FROM agent_schedules WHERE workspace_id = ANY($1::uuid[]) AND enabled = true", ids)
        recent_rows = await self._pool.fetch(
            """
            SELECT e.id, e.status, e.user_message, e.created_at, a.name AS agent_name
            FROM executions e
            JOIN agents a ON a.id = e.agent_id
            WHERE a.workspace_id = ANY($1::uuid[])
            ORDER BY e.created_at DESC
            LIMIT 8
            """,
            ids,
        )
        recent = [
            {
                "id": str(r["id"]),
                "agent_name": r["agent_name"],
                "status": r["status"],
                "user_message": (r["user_message"] or "")[:80],
                "created_at": r["created_at"].isoformat(),
            }
            for r in recent_rows
        ]
        return {
            "counts": {
                "agents": int(agents or 0),
                "executions": int(executions or 0),
                "knowledge": int(knowledge or 0),
                "pending_proposals": int(proposals or 0),
                "episodic_memories": int(episodic or 0),
                "active_schedules": int(schedules or 0),
            },
            "recent_executions": recent,
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
            workspace_id,
            agent_id,
            user_id,
            cron_expr,
            prompt_template,
            delivery_type,
            delivery_target,
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
            workspace_id,
            user_id,
        )

    async def list_enabled_schedules(self) -> list[asyncpg.Record]:
        return await self._pool.fetch("SELECT * FROM agent_schedules WHERE enabled = true")

    async def update_schedule_enabled(self, schedule_id: UUID, enabled: bool) -> None:
        await self._pool.execute(
            "UPDATE agent_schedules SET enabled = $1 WHERE id = $2",
            enabled,
            schedule_id,
        )

    async def update_schedule_last_run(self, schedule_id: UUID) -> None:
        await self._pool.execute(
            "UPDATE agent_schedules SET last_run_at = now() WHERE id = $1",
            schedule_id,
        )

    async def delete_agent_schedule(self, schedule_id: UUID, workspace_id: UUID) -> bool:
        result = await self._pool.execute(
            "DELETE FROM agent_schedules WHERE id = $1 AND workspace_id = $2",
            schedule_id,
            workspace_id,
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

    # ── Agent Skills ──────────────────────────────────────────────────────

    async def increment_skill_use(self, skill_id: UUID) -> None:
        await self._pool.execute(
            "UPDATE agent_skills SET use_count = use_count + 1 WHERE id = $1",
            skill_id,
        )

    async def get_skill_by_id(self, skill_id: UUID) -> asyncpg.Record | None:
        """Full skill row including content_md, parsed fields, score, use_count."""
        return await self._pool.fetchrow(
            """
            SELECT id, agent_id, workspace_id, name, version, content_md,
                   description, allowed_tools, triggers, metadata,
                   active, score, use_count, created_at
            FROM agent_skills
            WHERE id = $1
            """,
            skill_id,
        )

    async def list_skills_catalog(
        self,
        workspace_id: UUID,
        agent_id: UUID | None = None,
        q: str | None = None,
        category: str | None = None,
        limit: int = 200,
    ) -> list[asyncpg.Record]:
        """Cross-agent catalog of active skills with the owning agent name joined.

        Powers the Skills Hub. Returns active skills only; history is fetched
        via the existing get_skill_history per (agent_id, name).
        """
        return await self._pool.fetch(
            """
            SELECT s.id, s.agent_id, s.workspace_id, s.name, s.version,
                   s.content_md, s.description, s.allowed_tools, s.triggers,
                   s.metadata, s.active, s.score, s.use_count, s.created_at,
                   s.category,
                   a.name AS agent_name
            FROM agent_skills s
            JOIN agents a ON a.id = s.agent_id
            WHERE s.workspace_id = $1
              AND s.active = true
              AND ($2::uuid IS NULL OR s.agent_id = $2)
              AND ($3::text IS NULL
                   OR s.name ILIKE '%' || $3 || '%'
                   OR s.description ILIKE '%' || $3 || '%')
              AND ($5::text IS NULL OR s.category = $5)
            ORDER BY s.score DESC, s.use_count DESC, s.created_at DESC
            LIMIT $4
            """,
            workspace_id,
            agent_id,
            q,
            limit,
            category,
        )

    async def activate_skill_version(self, skill_id: UUID) -> asyncpg.Record | None:
        """Make this version active, deactivating siblings sharing (agent_id, name).

        Returns the activated row (or None if the id was unknown). Used by the
        Skills Hub's "Set active" action when reverting to a prior version.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT id, agent_id, name FROM agent_skills WHERE id = $1",
                skill_id,
            )
            if row is None:
                return None
            await conn.execute(
                "UPDATE agent_skills SET active = false WHERE agent_id = $1 AND name = $2 AND id <> $3",
                row["agent_id"],
                row["name"],
                skill_id,
            )
            return await conn.fetchrow(
                "UPDATE agent_skills SET active = true WHERE id = $1 "
                "RETURNING id, agent_id, workspace_id, name, version, content_md, "
                "         description, allowed_tools, triggers, metadata, "
                "         active, score, use_count, created_at",
                skill_id,
            )

    # ── Knowledge Graph ─────────────────────────────────────────────────────

    async def upsert_kg_node(
        self,
        workspace_id: UUID,
        label: str,
        node_type: str,
        source_path: str | None = None,
        content_hash: str | None = None,
        summary: str | None = None,
        embedding: list[float] | None = None,
        metadata: dict | None = None,
        cluster_id: int | None = None,
        pagerank: float = 0.0,
        pos_x: float = 0.0,
        pos_y: float = 0.0,
    ) -> UUID:
        import json as _json

        emb_str = _vec_literal(embedding) if embedding else None
        meta_str = _json.dumps(metadata or {})
        row = await self._pool.fetchrow(
            """
            INSERT INTO kg_nodes
              (workspace_id, label, node_type, source_path, content_hash, summary,
               embedding, metadata, cluster_id, pagerank, pos_x, pos_y, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,
                    CASE WHEN $7::text IS NULL THEN NULL ELSE $7::vector END,
                    $8::jsonb, $9, $10, $11, $12, now())
            ON CONFLICT (workspace_id, label, node_type) DO UPDATE SET
              source_path   = EXCLUDED.source_path,
              content_hash  = EXCLUDED.content_hash,
              summary       = EXCLUDED.summary,
              embedding     = EXCLUDED.embedding,
              metadata      = EXCLUDED.metadata,
              cluster_id    = EXCLUDED.cluster_id,
              pagerank      = EXCLUDED.pagerank,
              pos_x         = EXCLUDED.pos_x,
              pos_y         = EXCLUDED.pos_y,
              updated_at    = now()
            RETURNING id
            """,
            workspace_id,
            label,
            node_type,
            source_path,
            content_hash,
            summary,
            emb_str,
            meta_str,
            cluster_id,
            pagerank,
            pos_x,
            pos_y,
        )
        return row["id"]

    async def get_kg_node_by_label(self, workspace_id: UUID, label: str, node_type: str) -> asyncpg.Record | None:
        return await self._pool.fetchrow(
            "SELECT * FROM kg_nodes WHERE workspace_id=$1 AND label=$2 AND node_type=$3",
            workspace_id,
            label,
            node_type,
        )

    async def get_kg_node(self, node_id: UUID) -> asyncpg.Record | None:
        return await self._pool.fetchrow("SELECT * FROM kg_nodes WHERE id=$1", node_id)

    async def list_kg_nodes(self, workspace_id: UUID) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            "SELECT * FROM kg_nodes WHERE workspace_id=$1 ORDER BY pagerank DESC",
            workspace_id,
        )

    async def list_kg_nodes_by_types(self, workspace_id: UUID, node_types: list[str]) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            "SELECT * FROM kg_nodes WHERE workspace_id=$1 AND node_type = ANY($2::text[]) ORDER BY pagerank DESC",
            workspace_id,
            node_types,
        )

    async def list_kg_edges(self, workspace_id: UUID) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            "SELECT * FROM kg_edges WHERE workspace_id=$1",
            workspace_id,
        )

    async def upsert_kg_edge(
        self,
        workspace_id: UUID,
        source_id: UUID,
        target_id: UUID,
        edge_type: str,
        weight: float = 1.0,
        metadata: dict | None = None,
    ) -> UUID:
        import json as _json

        row = await self._pool.fetchrow(
            """
            INSERT INTO kg_edges (workspace_id, source_id, target_id, edge_type, weight, metadata)
            VALUES ($1,$2,$3,$4,$5,$6::jsonb)
            ON CONFLICT (source_id, target_id, edge_type) DO UPDATE SET
              weight   = EXCLUDED.weight,
              metadata = EXCLUDED.metadata
            RETURNING id
            """,
            workspace_id,
            source_id,
            target_id,
            edge_type,
            weight,
            _json.dumps(metadata or {}),
        )
        return row["id"]

    async def get_kg_neighbors(self, node_id: UUID, workspace_id: UUID) -> tuple[list[asyncpg.Record], list[asyncpg.Record]]:
        """Return (neighbor_nodes, edges) for 1-hop neighborhood."""
        edges = await self._pool.fetch(
            """
            SELECT * FROM kg_edges
            WHERE workspace_id=$1 AND (source_id=$2 OR target_id=$2)
            """,
            workspace_id,
            node_id,
        )
        neighbor_ids = set()
        for e in edges:
            neighbor_ids.add(e["source_id"])
            neighbor_ids.add(e["target_id"])
        neighbor_ids.discard(node_id)
        nodes = (
            await self._pool.fetch(
                "SELECT * FROM kg_nodes WHERE id = ANY($1::uuid[])",
                list(neighbor_ids),
            )
            if neighbor_ids
            else []
        )
        return list(nodes), list(edges)

    async def bulk_update_kg_metrics(
        self,
        pageranks: dict[UUID, float],
        clusters: dict[UUID, int],
        positions: dict[UUID, tuple[float, float]],
    ) -> None:
        """Bulk-write pagerank, cluster_id, pos_x, pos_y after NetworkX recompute."""
        if not pageranks:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(
                """
                UPDATE kg_nodes
                SET pagerank=($1)::float, cluster_id=($2)::int,
                    pos_x=($3)::float, pos_y=($4)::float
                WHERE id=$5
                """,
                [(pageranks.get(nid, 0.0), clusters.get(nid), *positions.get(nid, (0.0, 0.0)), nid) for nid in pageranks],
            )

    async def vector_search_kg(self, workspace_id: UUID, embedding: list[float], k: int = 6) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            """
            SELECT id, label, node_type, summary, source_path, metadata,
                   embedding <=> $1::vector AS dist
            FROM kg_nodes
            WHERE workspace_id=$2 AND embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $3
            """,
            _vec_literal(embedding),
            workspace_id,
            k,
        )

    async def delete_kg_node(self, workspace_id: UUID, node_id: UUID) -> bool:
        result = await self._pool.execute(
            "DELETE FROM kg_nodes WHERE id=$1 AND workspace_id=$2",
            node_id,
            workspace_id,
        )
        return result.endswith("1")

    async def insert_trace_node(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        execution_id: UUID,
        question: str,
        answer_summary: str,
        confidence: float,
        embedding: list[float] | None = None,
    ) -> UUID:
        """Create a trace node in the KG for this execution."""
        label = f"Run: {question[:60]}"
        vec = _vec_literal(embedding) if embedding else None
        metadata = json.dumps(
            {
                "agent_id": str(agent_id),
                "execution_id": str(execution_id),
                "confidence": confidence,
                "answer_preview": answer_summary[:300],
            }
        )
        row = await self._pool.fetchrow(
            """
            INSERT INTO kg_nodes (workspace_id, label, node_type, summary, embedding, metadata)
            VALUES ($1, $2, 'trace', $3, $4::vector, $5::jsonb)
            ON CONFLICT (workspace_id, label, node_type) DO UPDATE SET
                summary = EXCLUDED.summary,
                metadata = EXCLUDED.metadata,
                updated_at = now()
            RETURNING id
            """,
            workspace_id,
            label,
            answer_summary[:500],
            vec,
            metadata,
        )
        assert row is not None
        return row["id"]

    async def insert_trace_edges(self, workspace_id: UUID, trace_node_id: UUID, fact_node_ids: list[UUID]) -> None:
        """Link trace node to fact/concept nodes it produced."""
        for fid in fact_node_ids:
            await self._pool.execute(
                """
                INSERT INTO kg_edges (workspace_id, source_id, target_id, edge_type, weight)
                VALUES ($1, $2, $3, 'referenced_by', 1.0)
                ON CONFLICT DO NOTHING
                """,
                workspace_id,
                trace_node_id,
                fid,
            )

    # ── Agent Skills ─────────────────────────────────────────────────────

    async def upsert_agent_skill(
        self,
        agent_id: UUID,
        workspace_id: UUID,
        name: str,
        content_md: str,
        *,
        category: str = "General",
        initial_active: bool = True,
    ) -> UUID:
        """Insert a new version of a skill (append-only versioning).

        When initial_active=False the new version is created as inactive (candidate).
        The caller is responsible for activating it later (e.g., after proposal approval).
        """
        row = await self._pool.fetchrow(
            "SELECT COALESCE(MAX(version), 0) as max_v FROM agent_skills WHERE agent_id=$1 AND name=$2",
            agent_id,
            name,
        )
        next_version = (row["max_v"] if row else 0) + 1
        if initial_active:
            await self._pool.execute(
                "UPDATE agent_skills SET active = false WHERE agent_id=$1 AND name=$2",
                agent_id,
                name,
            )
        new_row = await self._pool.fetchrow(
            """
            INSERT INTO agent_skills (agent_id, workspace_id, name, version, content_md, category, active)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            agent_id,
            workspace_id,
            name,
            next_version,
            content_md,
            category or "General",
            initial_active,
        )
        assert new_row is not None
        return new_row["id"]

    async def list_active_skills(self, agent_id: UUID, workspace_id: UUID) -> list[asyncpg.Record]:
        """Get all active skill versions for an agent."""
        return await self._pool.fetch(
            """
            SELECT id, name, version, content_md, created_at
            FROM agent_skills
            WHERE agent_id = $1 AND workspace_id = $2 AND active = true
            ORDER BY name
            """,
            agent_id,
            workspace_id,
        )

    async def get_skill_history(self, agent_id: UUID, name: str) -> list[asyncpg.Record]:
        return await self._pool.fetch(
            "SELECT id, version, content_md, active, created_at FROM agent_skills WHERE agent_id=$1 AND name=$2 ORDER BY version DESC",
            agent_id,
            name,
        )

    async def decay_skill_scores(self, agent_id: UUID, workspace_id: UUID, decay_factor: float = 0.95) -> int:
        """Decay all active skill scores. Returns count of pruned skills (score < 0.3 after 10 uses)."""
        await self._pool.execute(
            "UPDATE agent_skills SET score = score * $1 WHERE agent_id=$2 AND workspace_id=$3 AND active=true",
            decay_factor,
            agent_id,
            workspace_id,
        )
        result = await self._pool.execute(
            "UPDATE agent_skills SET active = false WHERE agent_id=$1 AND workspace_id=$2 AND active=true AND score < 0.3 AND use_count >= 10",
            agent_id,
            workspace_id,
        )
        try:
            return int(result.split(" ")[1])
        except Exception:
            return 0

    async def boost_skill_score(self, skill_id: UUID, boost: float = 0.1) -> None:
        """Boost a skill's score when it leads to a good reflection grade."""
        await self._pool.execute(
            "UPDATE agent_skills SET score = LEAST(score + $1, 2.0) WHERE id = $2",
            boost,
            skill_id,
        )

    async def set_golden_item_skill(self, item_id: UUID, skill_id: UUID | None) -> None:
        """Link (or unlink) a golden_items row to a specific skill."""
        await self._pool.execute(
            "UPDATE golden_items SET skill_id = $1 WHERE id = $2",
            skill_id,
            item_id,
        )

    async def list_golden_items_for_skill(self, skill_id: UUID) -> list[asyncpg.Record]:
        """Return all golden_items linked to a skill (for rewriter / per-skill eval)."""
        return await self._pool.fetch(
            "SELECT id, set_id, input_text, expected_output, scoring_criteria, created_at FROM golden_items WHERE skill_id = $1 ORDER BY created_at",
            skill_id,
        )

    async def log_skill_match(
        self,
        skill_id: UUID,
        workspace_id: UUID,
        execution_id: UUID | None = None,
        matched_text: str | None = None,
    ) -> None:
        """Insert a skill_execution_events row. Fire-and-forget — callers should not await failures."""
        await self._pool.execute(
            """
            INSERT INTO skill_execution_events (skill_id, execution_id, workspace_id, matched_text)
            VALUES ($1, $2, $3, $4)
            """,
            skill_id,
            execution_id,
            workspace_id,
            matched_text,
        )

    async def count_skill_events_by_day(
        self,
        skill_id: UUID,
        window_days: int = 7,
    ) -> list[asyncpg.Record]:
        """Return daily match counts for the last N days (date, count columns)."""
        return await self._pool.fetch(
            """
            SELECT date_trunc('day', created_at)::date AS date, count(*)::int AS count
            FROM skill_execution_events
            WHERE skill_id = $1
              AND created_at >= now() - ($2 || ' days')::interval
            GROUP BY 1
            ORDER BY 1
            """,
            skill_id,
            str(window_days),
        )

    # ── Agent Versions ────────────────────────────────────────────────────

    async def get_version_by_proposal(self, proposal_id: UUID) -> asyncpg.Record | None:
        return await self._pool.fetchrow(
            "SELECT * FROM agent_versions WHERE proposal_id = $1 AND status = 'candidate' LIMIT 1",
            proposal_id,
        )

    async def insert_skill_node(self, workspace_id: UUID, agent_id: UUID, skill_name: str, skill_version: int, description: str) -> UUID:
        """Create/update a skill node in the KG."""
        label = f"Skill: {skill_name} v{skill_version}"
        metadata = json.dumps({"agent_id": str(agent_id), "version": skill_version})
        row = await self._pool.fetchrow(
            """
            INSERT INTO kg_nodes (workspace_id, label, node_type, summary, metadata)
            VALUES ($1, $2, 'skill', $3, $4::jsonb)
            ON CONFLICT (workspace_id, label, node_type) DO UPDATE SET
                summary = EXCLUDED.summary, metadata = EXCLUDED.metadata, updated_at = now()
            RETURNING id
            """,
            workspace_id,
            label,
            description[:500],
            metadata,
        )
        assert row is not None
        return row["id"]

    async def insert_tool_call_node(
        self,
        workspace_id: UUID,
        execution_id: UUID,
        tool_name: str,
        input_preview: str,
        output_preview: str,
        duration_ms: int,
    ) -> UUID:
        """Create a tool_call node for a tool invocation."""
        label = f"Tool: {tool_name} ({str(execution_id)[:8]})"
        metadata = json.dumps(
            {
                "execution_id": str(execution_id),
                "tool": tool_name,
                "input_preview": input_preview[:200],
                "duration_ms": duration_ms,
            }
        )
        row = await self._pool.fetchrow(
            """
            INSERT INTO kg_nodes (workspace_id, label, node_type, summary, metadata)
            VALUES ($1, $2, 'tool_call', $3, $4::jsonb)
            ON CONFLICT (workspace_id, label, node_type) DO UPDATE SET
                summary = EXCLUDED.summary, metadata = EXCLUDED.metadata, updated_at = now()
            RETURNING id
            """,
            workspace_id,
            label,
            output_preview[:500],
            metadata,
        )
        assert row is not None
        return row["id"]

    async def insert_metacog_node(
        self,
        workspace_id: UUID,
        execution_id: UUID,
        grade: int,
        issue: str | None,
        skill_created: str | None,
        prediction: str | None = None,
    ) -> UUID:
        """Create a metacognition node from reflector output."""
        label = f"Metacog: grade={grade} ({str(execution_id)[:8]})"
        metadata = json.dumps(
            {
                "execution_id": str(execution_id),
                "grade": grade,
                "issue": issue,
                "skill_created": skill_created,
                "prediction": prediction,
            }
        )
        summary = f"Grade: {grade}/5"
        if issue:
            summary += f" | Issue: {issue}"
        if skill_created:
            summary += f" | Created skill: {skill_created}"
        if prediction:
            summary += f" | Prediction: {prediction[:80]}"
        row = await self._pool.fetchrow(
            """
            INSERT INTO kg_nodes (workspace_id, label, node_type, summary, metadata)
            VALUES ($1, $2, 'metacog', $3, $4::jsonb)
            ON CONFLICT (workspace_id, label, node_type) DO UPDATE SET
                summary = EXCLUDED.summary, metadata = EXCLUDED.metadata, updated_at = now()
            RETURNING id
            """,
            workspace_id,
            label,
            summary[:500],
            metadata,
        )
        assert row is not None
        return row["id"]

    # ── JEPA Predictions ──────────────────────────────────────────────────

    async def store_prediction(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        user_id: UUID,
        prediction: str,
        execution_id: UUID,
    ) -> None:
        """Store a JEPA prediction for the next turn. Uses episodic_memories with [PREDICTION] prefix."""
        await self._pool.execute(
            """
            INSERT INTO episodic_memories (workspace_id, agent_id, user_id, execution_id, content)
            VALUES ($1, $2, $3, $4, $5)
            """,
            workspace_id,
            agent_id,
            user_id,
            execution_id,
            f"[PREDICTION] {prediction}",
        )

    async def get_latest_prediction(self, workspace_id: UUID, agent_id: UUID) -> str | None:
        """Get the most recent JEPA prediction for this agent."""
        row = await self._pool.fetchrow(
            """
            SELECT content FROM episodic_memories
            WHERE workspace_id = $1 AND agent_id = $2 AND content LIKE '[PREDICTION]%'
            ORDER BY created_at DESC LIMIT 1
            """,
            workspace_id,
            agent_id,
        )
        if row:
            return row["content"].removeprefix("[PREDICTION] ")
        return None

    async def list_kg_topics(self, workspace_id: UUID) -> list[str]:
        rows = await self._pool.fetch(
            "SELECT label FROM kg_nodes WHERE workspace_id=$1 AND node_type='topic' ORDER BY pagerank DESC LIMIT 30",
            workspace_id,
        )
        return [r["label"] for r in rows]
