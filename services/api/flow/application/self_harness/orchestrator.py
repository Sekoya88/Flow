"""Stage 4 — Orchestration: one Self-Harness round for one agent.

Mine held-in weaknesses -> propose K bounded edits -> validate each on held-in/
held-out -> merge accepted -> auto-promote a new genome (gated on MEASURED
non-regression, not proposer confidence). Every candidate is logged; an all-reject
round leaves the genome untouched.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any
from uuid import UUID, uuid4

from flow.application.self_harness.mutations import apply_edit
from flow.application.self_harness.proposer import propose_edits
from flow.application.self_harness.store import get_split_items, log_edit
from flow.application.self_harness.types import CONFIG_SURFACES, accept
from flow.application.self_harness.validator import eval_config_on_split, validate_edit
from flow.application.self_harness.weakness_miner import mine_weaknesses

logger = logging.getLogger(__name__)


async def _live_config(pool: Any, agent_id: UUID, workspace_id: UUID) -> dict | None:
    row = await pool.fetchrow(
        "SELECT config FROM agents WHERE id = $1 AND workspace_id = $2",
        agent_id,
        workspace_id,
    )
    if row is None:
        return None
    raw = row["config"]
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw) if raw else {}


async def _auto_promote(
    pool: Any,
    agent_id: UUID,
    workspace_id: UUID,
    user_id: UUID,
    merged_config: dict,
    *,
    pass_rate: float,
    summary: str,
) -> UUID:
    """Snapshot ``merged_config`` as the active genome and write an audit proposal.

    Mirrors curator._auto_activate_candidate but the gate here is empirical
    non-regression, not the proposer's self-rated confidence.
    """
    import datetime

    from flow.application.genome_service import activate_genome, get_active_genome, snapshot_genome
    from flow.domain.genome import VersionStatus, VersionTrigger

    parent = await get_active_genome(pool, agent_id)
    parent_id = parent.id if parent else None

    # snapshot_genome reads agents.config, so stage the merged config first.
    await pool.execute(
        "UPDATE agents SET config = $1 WHERE id = $2 AND workspace_id = $3",
        merged_config,
        agent_id,
        workspace_id,
    )
    candidate_id = await snapshot_genome(
        pool=pool,
        agent_id=agent_id,
        workspace_id=workspace_id,
        trigger=VersionTrigger.SELF_HARNESS,
        status=VersionStatus.CANDIDATE,
        pass_rate=pass_rate,
    )
    await activate_genome(pool, candidate_id, agent_id, workspace_id)

    if parent_id is not None:
        await pool.execute(
            "UPDATE agent_versions SET parent_id = $1, auto_promoted_at = $2 WHERE id = $3",
            parent_id,
            datetime.datetime.now(datetime.UTC),
            candidate_id,
        )

    await pool.execute(
        """INSERT INTO proposals (id, workspace_id, user_id, title, body, status, auto_approved)
           VALUES ($1, $2, $3, $4, $5, 'approved', TRUE)""",
        uuid4(),
        workspace_id,
        user_id,
        "[Self-Harness] Auto-promoted harness edit(s)",
        summary,
    )
    return candidate_id


async def run_self_harness_round(
    pool: Any,
    agent_id: UUID,
    workspace_id: UUID,
    golden_set_id: UUID,
    user_id: UUID,
    *,
    llm: Any = None,
    judge_client: Any = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    k: int = 3,
    max_items_per_split: int = 8,
) -> dict:
    """Run one full Self-Harness round. Returns a status dict."""
    round_id = uuid4()

    current_config = await _live_config(pool, agent_id, workspace_id)
    if current_config is None:
        return {"status": "no_agent", "round_id": str(round_id)}

    held_in, held_out = await get_split_items(pool, golden_set_id)
    held_in, held_out = held_in[:max_items_per_split], held_out[:max_items_per_split]
    if not held_in or not held_out:
        return {"status": "insufficient_split", "round_id": str(round_id)}

    bundle = await mine_weaknesses(pool, agent_id, llm=llm)
    if not bundle.patterns:
        return {"status": "no_weakness", "round_id": str(round_id)}

    edits = await propose_edits(current_config, bundle, llm=llm, allowed_surfaces=CONFIG_SURFACES, k=k)
    if not edits:
        return {"status": "no_proposals", "round_id": str(round_id)}

    eval_kwargs = {
        "judge_client": judge_client,
        "openai_api_key": openai_api_key,
        "anthropic_api_key": anthropic_api_key,
    }
    baseline_in = await eval_config_on_split(pool, workspace_id, agent_id, user_id, current_config, held_in, **eval_kwargs)
    baseline_ho = await eval_config_on_split(pool, workspace_id, agent_id, user_id, current_config, held_out, **eval_kwargs)

    accepted: list[dict] = []
    for edit in edits:
        if edit.surface not in CONFIG_SURFACES:
            await log_edit(pool, round_id, agent_id, workspace_id, edit, delta_in=None, delta_ho=None, accepted=False)
            continue
        res = await validate_edit(
            pool,
            workspace_id,
            agent_id,
            user_id,
            current_config,
            edit,
            held_in,
            held_out,
            baseline_in=baseline_in,
            baseline_ho=baseline_ho,
            **eval_kwargs,
        )
        await log_edit(pool, round_id, agent_id, workspace_id, edit, delta_in=res["delta_in"], delta_ho=res["delta_ho"], accepted=res["accepted"])
        if res["accepted"]:
            accepted.append({"edit": edit, **res})

    if not accepted:
        return {"status": "all_rejected", "round_id": str(round_id), "n_candidates": len(edits)}

    # Merge accepted edits. Verify the merged config as a whole still satisfies the
    # non-regression rule (merged edits can interact); if not, fall back to the
    # single best individually-validated edit.
    merged = copy.deepcopy(current_config)
    for a in accepted:
        merged = apply_edit(merged, a["edit"])

    if len(accepted) > 1:
        m_in = await eval_config_on_split(pool, workspace_id, agent_id, user_id, merged, held_in, **eval_kwargs)
        m_ho = await eval_config_on_split(pool, workspace_id, agent_id, user_id, merged, held_out, **eval_kwargs)
        if not accept(m_in - baseline_in, m_ho - baseline_ho):
            best = max(accepted, key=lambda a: a["delta_in"] + a["delta_ho"])
            merged = best["candidate_config"]
            m_ho = best["candidate_pass_ho"]
    else:
        m_ho = accepted[0]["candidate_pass_ho"]

    summary = (
        f"Self-Harness round {round_id}: {len(accepted)}/{len(edits)} edit(s) passed the "
        f"held-out non-regression gate (held-out pass {baseline_ho:.2f} -> {m_ho:.2f}). "
        f"Edits: {', '.join(a['edit'].target for a in accepted)}."
    )
    candidate_id = await _auto_promote(pool, agent_id, workspace_id, user_id, merged, pass_rate=m_ho, summary=summary)

    logger.info(
        "self_harness.promoted",
        extra={"agent_id": str(agent_id), "candidate_id": str(candidate_id), "n_accepted": len(accepted)},
    )
    return {
        "status": "promoted",
        "round_id": str(round_id),
        "candidate_id": str(candidate_id),
        "n_accepted": len(accepted),
        "n_candidates": len(edits),
        "baseline_ho": baseline_ho,
        "new_ho": m_ho,
    }


def _self_harness_enabled(raw_config: Any) -> bool:
    if isinstance(raw_config, str):
        try:
            raw_config = json.loads(raw_config)
        except Exception:
            return False
    return bool(isinstance(raw_config, dict) and raw_config.get("self_harness_enabled"))


async def self_harness_tick(ctx: dict) -> None:
    """Cron (nightly, after auto_eval_tick): run one Self-Harness round per opted-in agent.

    Opt-in via agents.config.self_harness_enabled. Best-effort per agent so one
    failure never aborts the sweep. Requires an OpenAI key + a golden set.
    """
    import os

    pool = ctx.get("pool")
    if pool is None:
        return
    openai_key = os.environ.get("FLOW_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        logger.info("self_harness.skip", extra={"reason": "no_openai_key"})
        return

    from langchain_openai import ChatOpenAI
    from openai import AsyncOpenAI

    llm = ChatOpenAI(api_key=openai_key, model="gpt-4o-mini", temperature=0.3)
    judge_client = AsyncOpenAI(api_key=openai_key)

    agents = await pool.fetch("SELECT id, workspace_id, config FROM agents")
    for agent in agents:
        if not _self_harness_enabled(agent["config"]):
            continue
        ws_id = agent["workspace_id"]
        gset = await pool.fetchrow("SELECT id FROM golden_sets WHERE workspace_id = $1 LIMIT 1", ws_id)
        if not gset:
            continue
        owner = await pool.fetchrow(
            "SELECT user_id FROM workspace_members WHERE workspace_id = $1 ORDER BY (role = 'owner') DESC LIMIT 1",
            ws_id,
        )
        if not owner:
            continue
        try:
            result = await run_self_harness_round(
                pool,
                agent["id"],
                ws_id,
                gset["id"],
                owner["user_id"],
                llm=llm,
                judge_client=judge_client,
                openai_api_key=openai_key,
            )
            logger.info("self_harness.round_done", extra={"agent_id": str(agent["id"]), **result})
        except Exception as exc:
            logger.warning("self_harness.agent_failed agent_id=%s error=%s", agent["id"], exc)
