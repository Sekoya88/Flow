"""Curator — orchestrates the self-improvement feedback loop.

Two entry points:
  • `maybe_spawn_proposal` — reacts to low user-feedback scores on executions.
  • `check_regression_and_propose` — reacts to golden-set eval failures.

Autonomous mode (Milestone F):
  When agent.auto_improve_threshold is set (not NULL), the curator skips
  the human-approval proposal and directly activates the CANDIDATE genome,
  provided the rewrite confidence >= 0.5. An audit-trail entry is written
  to the proposals table with auto_approved=TRUE.

Manual mode (default, threshold=NULL):
  eval failure → root-cause analysis → prompt rewrite → candidate genome
  → proposal to promote → human approval → activate
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from langchain_core.messages import HumanMessage, SystemMessage

from flow.infrastructure.persistence.repo import FlowRepository

logger = logging.getLogger(__name__)


async def maybe_spawn_proposal(
    *,
    repo: FlowRepository,
    workspace_id: UUID,
    agent_id: UUID,
    user_id: UUID,
    execution_id: UUID,
    score: float,
    openai_api_key: str | None,
) -> UUID | None:
    """Create a curator proposal and agent negative for low-score executions."""
    if score >= 0.4:
        return None

    # Insert agent negative so worker avoids repeating this mistake
    try:
        await repo.insert_agent_negative(
            workspace_id,
            agent_id,
            content=f"Execution {execution_id} received low feedback score {score:.2f}. Review and avoid similar responses.",
            source="feedback",
        )
    except Exception:
        pass

    title = "Flow curator: improve recent run"
    if openai_api_key:
        from flow.infrastructure.llm.providers import get_chat_model

        llm = get_chat_model(
            {"provider": "openai", "model": "gpt-5.4-mini", "temperature": 0.3},
            fallback_api_keys={"openai": openai_api_key},
        )
        out = await llm.ainvoke(
            [
                SystemMessage(
                    content=(
                        "User rated an agent execution low. Propose one concrete improvement "
                        "(prompt tweak, new knowledge to upload, or a skill). Max 120 words."
                    )
                ),
                HumanMessage(content=f"execution_id={execution_id} score={score}. Write the proposal body."),
            ]
        )
        body = str(out.content)
    else:
        body = (
            "Low execution score without LLM. Consider adding OPENAI_API_KEY, "
            "uploading knowledge sources, or tightening the user goal in the first message."
        )
    return await repo.create_proposal(workspace_id, user_id, title, body, execution_id=execution_id)


async def _get_agent_auto_threshold(pool, agent_id: UUID) -> tuple[float | None, float]:
    """Return (auto_improve_threshold, auto_improve_rollback_delta) for an agent."""
    row = await pool.fetchrow(
        "SELECT auto_improve_threshold, auto_improve_rollback_delta FROM agents WHERE id = $1",
        agent_id,
    )
    if row is None:
        return None, 0.15
    return row["auto_improve_threshold"], (row["auto_improve_rollback_delta"] or 0.15)


async def _auto_activate_candidate(
    pool,
    candidate_id: str,
    agent_id: UUID,
    workspace_id: UUID,
    user_id: UUID,
    title: str,
    body: str,
) -> None:
    """Directly activate a CANDIDATE genome and write an audit-trail proposal."""
    import datetime
    from uuid import UUID as _UUID

    from flow.application.genome_service import activate_genome

    cid = _UUID(candidate_id)
    await activate_genome(pool, cid, agent_id, workspace_id)

    # Mark auto_promoted_at on the now-active version
    await pool.execute(
        "UPDATE agent_versions SET auto_promoted_at = $1 WHERE id = $2",
        datetime.datetime.now(datetime.UTC),
        cid,
    )

    # Audit trail — auto_approved=TRUE so the UI can distinguish it from manual proposals
    audit_id = uuid4()
    await pool.execute(
        """
        INSERT INTO proposals (id, workspace_id, user_id, title, body, status, auto_approved)
        VALUES ($1, $2, $3, $4, $5, 'approved', TRUE)
        """,
        audit_id,
        workspace_id,
        user_id,
        f"[Auto-approved] {title}",
        body,
    )
    logger.info(
        "curator.auto_activated",
        extra={
            "agent_id": str(agent_id),
            "candidate_id": candidate_id,
            "audit_proposal_id": str(audit_id),
        },
    )


async def check_regression_and_propose(
    pool,
    golden_set_id: UUID,
    agent_id: UUID,
    new_avg_score: float,
    results: list[dict],
    workspace_id: UUID,
    user_id: UUID,
    openai_api_key: str | None = None,
) -> dict | None:
    """Check if the latest evaluation regressed, or if specific items failed.

    If failures are found:
      1. Call the Prompt Rewriter to generate an improved system prompt
      2. Snapshot as a CANDIDATE genome
      3. If agent.auto_improve_threshold is set and confidence >= 0.5 and
         threshold is met → auto-activate (Milestone F: autonomous mode)
      4. Otherwise → create a human-approval proposal

    Returns a dict with rewrite info, or None if no action taken.
    """
    from flow.infrastructure.persistence.repo import FlowRepository

    repo = FlowRepository(pool)

    auto_threshold, _rollback_delta = await _get_agent_auto_threshold(pool, agent_id)

    failed_items = [r for r in results if r.get("score") is not None and r["score"] < 0.7]

    # 1. Basic regression alert (manual mode only — no alert spam in auto mode)
    if new_avg_score < 0.7 and auto_threshold is None:
        title = "Regression Alert: Golden Set Score Drop"
        body = f"The agent scored {new_avg_score:.2f} on golden set {golden_set_id}. This is below the 0.7 threshold. Please review the failed items."
        await repo.create_proposal(workspace_id, user_id, title, body)

    # 2. Autonomous Prompt Rewrite (the self-improvement loop)
    if failed_items and openai_api_key:
        from flow.application.genome_service import get_active_genome
        from flow.application.prompt_rewriter import FailedItem, rewrite_and_snapshot

        active_genome = await get_active_genome(pool, agent_id)
        current_prompt = active_genome.system_prompt if active_genome else ""
        llm_config = {}
        if active_genome:
            llm_config = {
                "provider": active_genome.llm_config.provider,
                "model": active_genome.llm_config.model,
                "temperature": active_genome.llm_config.temperature,
            }

        failed_for_rewrite = [
            FailedItem(
                input_text=r.get("input_text", ""),
                expected_output=r.get("expected_output", ""),
                actual_output=r.get("actual_output", ""),
                score=r["score"],
                rationale=r.get("rationale", ""),
            )
            for r in failed_items
        ]

        try:
            rewrite_info = await rewrite_and_snapshot(
                pool=pool,
                agent_id=agent_id,
                workspace_id=workspace_id,
                user_id=user_id,
                current_prompt=current_prompt,
                failed_items=failed_for_rewrite,
                llm_config=llm_config,
                openai_api_key=openai_api_key,
            )

            if rewrite_info:
                candidate_id = rewrite_info["candidate_version_id"]
                changelog = rewrite_info["rewrite"]["changelog"]
                analysis = rewrite_info["rewrite"]["failure_analysis"]
                confidence = rewrite_info["rewrite"]["confidence"]

                title = f"Auto-improvement: {len(failed_items)} failures fixed (confidence: {confidence:.0%})"
                body = (
                    f"**Failure Analysis:** {analysis}\n\n"
                    f"**Changes Applied:**\n" + "\n".join(f"- {c}" for c in changelog) + f"\n\n**Candidate Version:** `{candidate_id}`\n"
                    f"**Confidence:** {confidence:.0%}"
                )

                # Autonomous mode: skip proposal, activate directly
                if auto_threshold is not None and confidence >= 0.5 and confidence >= auto_threshold:
                    await _auto_activate_candidate(
                        pool=pool,
                        candidate_id=candidate_id,
                        agent_id=agent_id,
                        workspace_id=workspace_id,
                        user_id=user_id,
                        title=title,
                        body=body + "\n\nPromote the improved prompt to production.",
                    )
                else:
                    # Manual mode: create a human-approval proposal
                    from uuid import UUID as _UUID

                    from flow.application.genome_service import _create_genome_proposal

                    await _create_genome_proposal(
                        pool=pool,
                        workspace_id=workspace_id,
                        user_id=user_id,
                        candidate_version_id=_UUID(candidate_id),
                        title=title,
                        body=body + "\n\nApprove this proposal to promote the improved prompt to production.",
                    )

                logger.info(
                    "curator.auto_improvement.completed",
                    extra={
                        "agent_id": str(agent_id),
                        "candidate_id": candidate_id,
                        "num_failures": len(failed_items),
                        "confidence": confidence,
                        "autonomous": auto_threshold is not None and confidence >= (auto_threshold or 1.0),
                    },
                )
                return rewrite_info

        except Exception:
            logger.warning("curator.auto_improvement.failed", exc_info=True)

    # 3. Fallback: LLM-generated textual suggestion for the worst failure
    if failed_items and openai_api_key:
        from flow.infrastructure.llm.providers import get_chat_model

        llm = get_chat_model(
            {"provider": "openai", "model": "gpt-5.4-mini", "temperature": 0.2},
            fallback_api_keys={"openai": openai_api_key},
        )

        worst = min(failed_items, key=lambda x: x["score"])

        try:
            out = await llm.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "An agent failed a test case. Analyze the failure and propose a new skill "
                            "(in SKILL.md format) or a prompt adjustment to fix this specific issue. "
                            "Keep it concise. Start directly with the proposed fix."
                        )
                    ),
                    HumanMessage(content=f"Question: {worst['input_text']}\nScore: {worst['score']}\nRationale: {worst['rationale']}"),
                ]
            )

            title = "Auto-refinement: Suggested Fix for Failed Test"
            body = str(out.content)
            await repo.create_proposal(workspace_id, user_id, title, body)
        except Exception:
            pass

    return None
