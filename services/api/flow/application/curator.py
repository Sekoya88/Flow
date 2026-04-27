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
