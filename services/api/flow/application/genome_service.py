from __future__ import annotations

import datetime
import logging
from uuid import UUID, uuid4

import asyncpg

from flow.domain.genome import AgentGenome, VersionStatus, VersionTrigger

logger = logging.getLogger(__name__)

_SCORE_EPSILON = 1e-9


def _auto_label(trigger: VersionTrigger) -> str:
    """Generate a human-readable version label from a trigger type."""
    now = datetime.datetime.now(datetime.timezone.utc)
    if trigger == VersionTrigger.SKILL_CREATED:
        return f"auto-skill-{now.strftime('%Y-%m-%dT%H:%M')}"
    elif trigger == VersionTrigger.EVAL_PASS:
        return f"auto-eval-{now.strftime('%Y-%m-%d')}"
    elif trigger == VersionTrigger.CONFIG_PATCH:
        return f"auto-config-{now.strftime('%Y-%m-%dT%H:%M')}"
    else:
        return f"v-{now.strftime('%Y-%m-%dT%H:%M')}"


async def snapshot_genome(
    pool: asyncpg.Pool,
    agent_id: UUID,
    workspace_id: UUID,
    trigger: VersionTrigger,
    version_label: str | None = None,
    created_by: UUID | None = None,
    status: VersionStatus = VersionStatus.ACTIVE,
    avg_score: float | None = None,
    pass_rate: float | None = None,
) -> UUID:
    """
    Read current agent config + active skills → write to agent_versions.
    Returns the new version UUID.

    Steps:
    1. Fetch agent row (config, template)
    2. Fetch active skills (id, name) ordered by score DESC
    3. Build config_snapshot: merge agent.config with _genome sub-object
    4. Auto-generate version_label if None
    5. INSERT into agent_versions
    """
    async with pool.acquire() as conn:
        agent_row = await conn.fetchrow(
            "SELECT config, template FROM agents WHERE id = $1 AND workspace_id = $2",
            agent_id, workspace_id,
        )
        if agent_row is None:
            raise ValueError(f"Agent {agent_id} not found in workspace {workspace_id}")

        skill_rows = await conn.fetch(
            "SELECT id, name FROM agent_skills "
            "WHERE agent_id = $1 AND workspace_id = $2 AND active = true "
            "ORDER BY score DESC",
            agent_id, workspace_id,
        )

        config = dict(agent_row["config"]) if agent_row["config"] else {}
        template = agent_row["template"] or config.get("template", "deer_flow")

        config["_genome"] = {
            "active_skill_ids": [str(r["id"]) for r in skill_rows],
            "active_skill_names": [r["name"] for r in skill_rows],
        }

        label = version_label or _auto_label(trigger)

        version_id = uuid4()
        await conn.execute(
            """
            INSERT INTO agent_versions
                (id, agent_id, version_label, config_snapshot, template,
                 created_by, status, trigger, avg_score, pass_rate)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            version_id,
            agent_id,
            label,
            config,
            template,
            created_by,
            status.value,
            trigger.value,
            avg_score,
            pass_rate,
        )

    logger.info(
        "genome.snapshot",
        extra={"agent_id": str(agent_id), "version_label": label,
               "trigger": trigger.value, "status": status.value},
    )
    return version_id


async def activate_genome(
    pool: asyncpg.Pool,
    version_id: UUID,
    agent_id: UUID,
    workspace_id: UUID,
) -> None:
    """
    Atomically promote a candidate/archived version to ACTIVE:
    1. Archive all current ACTIVE versions for this agent
    2. Set the target version to ACTIVE
    3. Apply config_snapshot back to agents.config
    All three steps in a single transaction.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE agent_versions SET status = 'archived' "
                "WHERE agent_id = $1 AND status = 'active' "
                "AND EXISTS (SELECT 1 FROM agents WHERE id = $1 AND workspace_id = $2)",
                agent_id, workspace_id,
            )
            row = await conn.fetchrow(
                "UPDATE agent_versions SET status = 'active' "
                "WHERE id = $1 AND agent_id = $2 RETURNING config_snapshot, template",
                version_id, agent_id,
            )
            if row is None:
                raise ValueError(f"Version {version_id} not found")

            await conn.execute(
                "UPDATE agents SET config = $1, template = $2 WHERE id = $3 AND workspace_id = $4",
                row["config_snapshot"],
                row["template"],
                agent_id,
                workspace_id,
            )

    logger.info(
        "genome.activated",
        extra={"version_id": str(version_id), "agent_id": str(agent_id)},
    )


async def load_genome(
    pool: asyncpg.Pool,
    version_id: UUID,
    agent_id: UUID,
) -> AgentGenome:
    """Reconstruct an AgentGenome from a persisted agent_versions row."""
    row = await pool.fetchrow(
        "SELECT * FROM agent_versions WHERE id = $1 AND agent_id = $2",
        version_id, agent_id,
    )
    if row is None:
        raise ValueError(f"Version {version_id} not found for agent {agent_id}")
    return _row_to_genome(row)


async def get_active_genome(
    pool: asyncpg.Pool,
    agent_id: UUID,
) -> AgentGenome | None:
    """Get the current ACTIVE version for an agent, or None if none exists."""
    row = await pool.fetchrow(
        "SELECT * FROM agent_versions WHERE agent_id = $1 AND status = 'active' "
        "ORDER BY created_at DESC LIMIT 1",
        agent_id,
    )
    return _row_to_genome(row) if row else None


async def get_previous_active_genome(
    pool: asyncpg.Pool,
    agent_id: UUID,
) -> AgentGenome | None:
    """Most recently archived version (was active before current)."""
    row = await pool.fetchrow(
        "SELECT * FROM agent_versions WHERE agent_id = $1 AND status = 'archived' "
        "ORDER BY created_at DESC LIMIT 1",
        agent_id,
    )
    return _row_to_genome(row) if row else None


async def _maybe_snapshot_eval_pass(
    pool: asyncpg.Pool,
    agent_id: UUID,
    workspace_id: UUID,
    user_id: UUID | None,
    avg_score: float,
    pass_rate: float,
) -> UUID | None:
    """
    Create a CANDIDATE genome snapshot only if the new avg_score beats the current
    ACTIVE version's avg_score (or if no active version has a score yet).
    Returns the new candidate UUID, or None if no improvement detected.
    """
    active = await get_active_genome(pool, agent_id)
    if active is not None and active.avg_score is not None:
        if avg_score <= active.avg_score + _SCORE_EPSILON:
            logger.debug(
                "genome.eval_pass.no_improvement",
                extra={"agent_id": str(agent_id),
                       "new_score": avg_score, "current_score": active.avg_score},
            )
            return None

    return await snapshot_genome(
        pool=pool,
        agent_id=agent_id,
        workspace_id=workspace_id,
        trigger=VersionTrigger.EVAL_PASS,
        created_by=user_id,
        status=VersionStatus.CANDIDATE,
        avg_score=avg_score,
        pass_rate=pass_rate,
    )


async def _create_genome_proposal(
    pool: asyncpg.Pool,
    workspace_id: UUID,
    user_id: UUID | None,
    candidate_version_id: UUID,
    title: str,
    body: str,
) -> UUID:
    """
    Create a proposal linked to a candidate genome version.
    Sets agent_versions.proposal_id = new proposal UUID.

    Note: workspaces table has no owner_id column — if user_id is None, the
    proposal cannot be created (proposals.user_id is NOT NULL).
    """
    proposal_id = uuid4()

    effective_user_id = user_id
    if effective_user_id is None:
        raise ValueError(
            f"Cannot create genome proposal for workspace {workspace_id}: "
            "no user_id provided and workspace has no owner"
        )

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO proposals (id, workspace_id, user_id, title, body, status)
                VALUES ($1, $2, $3, $4, $5, 'pending')
                """,
                proposal_id, workspace_id, effective_user_id, title, body,
            )

            await conn.execute(
                "UPDATE agent_versions SET proposal_id = $1 WHERE id = $2",
                proposal_id, candidate_version_id,
            )

    logger.info(
        "genome.proposal.created",
        extra={"proposal_id": str(proposal_id),
               "candidate_version_id": str(candidate_version_id)},
    )
    return proposal_id


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _row_to_genome(row: asyncpg.Record) -> AgentGenome:
    """Convert a raw agent_versions DB row to an AgentGenome dataclass."""
    import json
    from flow.domain.genome import ModelConfig

    config = row["config_snapshot"]
    if isinstance(config, str):
        config = json.loads(config)
    config = config or {}

    genome_meta = config.get("_genome") or {}
    llm_raw = config.get("llm_config") or config.get("model") or {}

    return AgentGenome.from_row({
        "id": row["id"],
        "agent_id": row["agent_id"],
        "version_label": row["version_label"],
        "template": row.get("template") or config.get("template", "deer_flow"),
        "system_prompt": config.get("system_prompt", ""),
        "llm_config": llm_raw,
        "tools": config.get("tools", {}),
        "active_skill_ids": [str(r) for r in (genome_meta.get("active_skill_ids") or [])],
        "active_skill_names": genome_meta.get("active_skill_names", []),
        "status": row.get("status", "active"),
        "trigger": row.get("trigger", "manual"),
        "created_by": row.get("created_by"),
        "created_at": row.get("created_at"),
        "avg_score": row.get("avg_score"),
        "pass_rate": row.get("pass_rate"),
        "proposal_id": row.get("proposal_id"),
    })
