"""Stage 3 — Proposal Validation.

Evaluate a candidate edit on the held-in and held-out splits by compiling the
candidate genome into the *actual* graph (so runtime-loops and tool edits take
effect, unlike the direct-invoke golden evaluator) and scoring each item with the
existing LLM judge. Promote only under the paper's non-regression accept rule.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from flow.application.golden_evaluator import judge_single
from flow.application.self_harness.mutations import apply_edit
from flow.application.self_harness.types import HarnessEdit, accept

logger = logging.getLogger(__name__)

PASS_THRESHOLD = 0.7


async def run_harness_on_item(
    pool: Any,
    workspace_id: UUID,
    agent_id: UUID,
    user_id: UUID,
    agent_config: dict,
    input_text: str,
    *,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
) -> str:
    """Compile ``agent_config`` into the deer-flow graph and run one item.

    Eval-only: no stream hub, no execution id, no persistence — nodes guard on
    those being None. Returns the final answer text.
    """
    from langchain_core.messages import HumanMessage

    from flow.infrastructure.graph.deer_graph import GraphContext, build_deer_flow_graph

    ctx = GraphContext(
        pool=pool,
        workspace_id=workspace_id,
        agent_id=agent_id,
        user_id=user_id,
        openai_api_key=openai_api_key,
        agent_config=agent_config,
        anthropic_api_key=anthropic_api_key,
        execution_id=None,
        stream_hub=None,
        store=None,
    )
    graph = build_deer_flow_graph(ctx)
    final = await graph.ainvoke(
        {"messages": [HumanMessage(content=input_text)]},
        config={"recursion_limit": 50},
    )

    answer = final.get("answer") or ""
    if not answer:
        for msg in reversed(final.get("messages") or []):
            content = getattr(msg, "content", "")
            if content and getattr(msg, "type", "") == "ai":
                answer = content if isinstance(content, str) else str(content)
                break
    return str(answer)


async def eval_config_on_split(
    pool: Any,
    workspace_id: UUID,
    agent_id: UUID,
    user_id: UUID,
    config: dict,
    items: list[dict],
    *,
    judge_client: Any = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
) -> float:
    """Run ``config`` over ``items`` and return the pass rate (score >= 0.7)."""
    if not items:
        return 0.0
    passed = 0
    for it in items:
        actual = await run_harness_on_item(
            pool,
            workspace_id,
            agent_id,
            user_id,
            config,
            it.get("input_text", ""),
            openai_api_key=openai_api_key,
            anthropic_api_key=anthropic_api_key,
        )
        judged = await judge_single(
            it.get("input_text", ""),
            it.get("expected_output", ""),
            actual,
            it.get("scoring_criteria"),
            client=judge_client,
        )
        if float(judged.get("score", 0.0)) >= PASS_THRESHOLD:
            passed += 1
    return passed / len(items)


async def validate_edit(
    pool: Any,
    workspace_id: UUID,
    agent_id: UUID,
    user_id: UUID,
    current_config: dict,
    edit: HarnessEdit,
    held_in: list[dict],
    held_out: list[dict],
    *,
    judge_client: Any = None,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    baseline_in: float | None = None,
    baseline_ho: float | None = None,
) -> dict:
    """Apply ``edit``, evaluate both splits, and decide accept/reject.

    Baselines (current config's pass rates) can be precomputed once per round and
    passed in to avoid re-evaluating the current harness for every candidate.
    Returns: candidate_config, delta_in, delta_ho, accepted, and the candidate
    pass rates.
    """
    kwargs = {
        "judge_client": judge_client,
        "openai_api_key": openai_api_key,
        "anthropic_api_key": anthropic_api_key,
    }

    if baseline_in is None:
        baseline_in = await eval_config_on_split(pool, workspace_id, agent_id, user_id, current_config, held_in, **kwargs)
    if baseline_ho is None:
        baseline_ho = await eval_config_on_split(pool, workspace_id, agent_id, user_id, current_config, held_out, **kwargs)

    candidate_config = apply_edit(current_config, edit)
    cand_in = await eval_config_on_split(pool, workspace_id, agent_id, user_id, candidate_config, held_in, **kwargs)
    cand_ho = await eval_config_on_split(pool, workspace_id, agent_id, user_id, candidate_config, held_out, **kwargs)

    delta_in = cand_in - baseline_in
    delta_ho = cand_ho - baseline_ho
    return {
        "candidate_config": candidate_config,
        "delta_in": delta_in,
        "delta_ho": delta_ho,
        "accepted": accept(delta_in, delta_ho),
        "candidate_pass_in": cand_in,
        "candidate_pass_ho": cand_ho,
    }
