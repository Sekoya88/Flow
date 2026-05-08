from __future__ import annotations

from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage

from flow.infrastructure.persistence.repo import FlowRepository


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
            {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.3},
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
                HumanMessage(
                    content=f"execution_id={execution_id} score={score}. Write the proposal body."
                ),
            ]
        )
        body = str(out.content)
    else:
        body = (
            "Low execution score without LLM. Consider adding OPENAI_API_KEY, "
            "uploading knowledge sources, or tightening the user goal in the first message."
        )
    return await repo.create_proposal(
        workspace_id, user_id, title, body, execution_id=execution_id
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
) -> None:
    """Check if the latest evaluation regressed, or if specific items failed.
    If so, generate a proposal to fix the skill/agent.
    """
    from flow.infrastructure.persistence.repo import FlowRepository
    repo = FlowRepository(pool)

    # 1. Check for regression against past evaluations
    # (Since we don't have a formal 'evaluation run' table, we can just alert on absolute low score for now,
    # or compare with recent results).
    
    if new_avg_score < 0.7:
        title = "Regression Alert: Golden Set Score Drop"
        body = f"The agent scored {new_avg_score:.2f} on golden set {golden_set_id}. This is below the 0.7 threshold. Please review the failed items."
        await repo.create_proposal(workspace_id, user_id, title, body)

    # 2. Skill Refinement for specific failures (Phase 4.1)
    failed_items = [r for r in results if r["score"] is not None and r["score"] < 0.7]
    if failed_items and openai_api_key:
        from flow.infrastructure.llm.providers import get_chat_model
        llm = get_chat_model(
            {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.2},
            fallback_api_keys={"openai": openai_api_key},
        )
        
        # Take the worst failed item
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
                    HumanMessage(
                        content=f"Question: {worst['input_text']}\nScore: {worst['score']}\nRationale: {worst['rationale']}"
                    ),
                ]
            )
            
            title = "Auto-refinement: Suggested Fix for Failed Test"
            body = str(out.content)
            await repo.create_proposal(workspace_id, user_id, title, body)
        except Exception:
            pass
