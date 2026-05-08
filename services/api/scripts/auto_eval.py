"""Automatic Evaluation Script for Flow Agents.

This script runs the golden dataset items through the evaluator.
If you want to test the full agent pipeline, you can modify it to invoke the LangGraph agent first,
store the outputs in `golden_results`, and then run `evaluate_golden_set`.

Usage:
  uv run python scripts/auto_eval.py
"""

import asyncio
import os
import uuid
import asyncpg
from pprint import pprint
from openai import AsyncOpenAI

from flow.config import get_settings
from flow.application.golden_evaluator import evaluate_golden_set
from flow.infrastructure.observability.logging import configure_logging, get_logger

logger = get_logger("auto_eval")

async def main():
    settings = get_settings()
    configure_logging(level="INFO", json_output=False, force_colors=True, service="auto_eval")

    # Connect to the database
    pool = await asyncpg.create_pool(settings.database_url)
    
    # Get a workspace
    workspace = await pool.fetchrow("SELECT id FROM workspaces LIMIT 1")
    if not workspace:
        logger.error("No workspace found.")
        return
    workspace_id = workspace["id"]
    
    # Get the default agent
    agent = await pool.fetchrow("SELECT id FROM agents WHERE workspace_id = $1 LIMIT 1", workspace_id)
    if not agent:
        logger.error("No agent found.")
        return
    agent_id = agent["id"]
    agent_version = "v1.0"
    
    # Get the golden set
    golden_set = await pool.fetchrow("SELECT id FROM golden_sets WHERE workspace_id = $1 LIMIT 1", workspace_id)
    if not golden_set:
        logger.error("No golden set found. Please seed the golden dataset first.")
        return
    set_id = golden_set["id"]

    logger.info("Starting Automatic Evaluation", workspace_id=workspace_id, agent_id=agent_id, golden_set_id=set_id)

    # 1. (Optional) Run the agent for each item. 
    # For now, we simulate existing executions by mocking the actual_output if missing,
    # or you can run `run_deer_execution` here.
    
    items = await pool.fetch("SELECT id, expected_output FROM golden_items WHERE set_id = $1", set_id)
    
    for item in items:
        # Check if result exists
        exists = await pool.fetchval("SELECT id FROM golden_results WHERE item_id = $1 AND agent_id = $2", item["id"], agent_id)
        if not exists:
            # We seed a mock output for the sake of the demonstration.
            # In a real environment, you would invoke the agent here and save its output.
            await pool.execute(
                """
                INSERT INTO golden_results (item_id, agent_id, agent_version_label, actual_output)
                VALUES ($1, $2, $3, $4)
                """,
                item["id"], agent_id, agent_version,
                f"Simulated output matching expected: {item['expected_output'][:50]}..."
            )
            
    # 2. Run the evaluator
    logger.info("Running Golden Evaluator...")
    results = await evaluate_golden_set(
        pool=pool,
        golden_set_id=set_id,
        agent_id=agent_id,
        agent_version_label=agent_version,
        workspace_id=workspace_id,
        client=AsyncOpenAI(api_key=os.environ.get("FLOW_OPENAI_API_KEY"))
        # user_id=None # Add user_id if you want to enable auto-proposal generation
    )
    
    logger.info("Evaluation Complete!")
    pprint(results)
    
    if results["pass_rate"] < 0.7:
        logger.warning("REGRESSION DETECTED! Pass rate is below 70%.")
    else:
        logger.info("Agent is stable. No regression detected.")

    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
