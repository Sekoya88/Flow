"""Golden sets CRUD + evaluation API."""
from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from flow.application.golden_evaluator import evaluate_golden_set
from flow.infrastructure.persistence.repo import FlowRepository
from flow.interfaces.http.deps import get_current_user_id, get_repo

# ── Sample datasets (imported lazily to avoid circular deps) ──────────

_SAMPLE_SETS = [
    {
        "name": "Research Analyst — Core Capabilities",
        "description": "Tests ability to synthesize academic sources and structure reports",
        "items": [
            {
                "input_text": "What are the latest advances in retrieval-augmented generation (RAG)?",
                "expected_output": "A structured report with: background, key findings citing at least 2 sources with confidence scores, identified limitations, and a conclusion.",
                "scoring_criteria": "Must include cited sources, structured findings, limitations, concrete conclusion. Score 0-10.",
            },
            {
                "input_text": "Summarize recent research on LLM alignment and safety techniques.",
                "expected_output": "Coverage of RLHF, Constitutional AI, DPO. Cite specific techniques. Acknowledge open problems.",
                "scoring_criteria": "Must cover main alignment techniques, cite specific papers, identify open problems.",
            },
            {
                "input_text": "What does recent research say about transformer scaling laws?",
                "expected_output": "Reference Chinchilla, explain compute-optimal training, note recent challenges to power-law assumptions.",
                "scoring_criteria": "Must reference Chinchilla, explain compute-optimal training, note recent challenges.",
            },
        ],
    },
    {
        "name": "Code Review Agent — Quality Assessment",
        "description": "Tests bug detection, security analysis, and fix suggestions",
        "items": [
            {
                "input_text": "Review this Python:\n```python\ndef get_user(uid):\n    conn = sqlite3.connect('app.db')\n    cursor = conn.cursor()\n    cursor.execute(f\"SELECT * FROM users WHERE id = {uid}\")\n    return cursor.fetchone()\n```",
                "expected_output": '{"language":"python","overall_verdict":"request_changes","score":2,"findings":[{"severity":"critical","category":"security","description":"SQL injection via f-string"}],"summary":"Critical SQL injection. Must fix."}',
                "scoring_criteria": "Must identify SQL injection as critical, provide parameterized query fix.",
            },
            {
                "input_text": "Review this React component:\n```tsx\nfunction List() {\n  const [items, setItems] = useState([]);\n  useEffect(() => { fetch('/api/items').then(r => r.json()).then(setItems); });\n  return <ul>{items.map(i => <li>{i.name}</li>)}</ul>;\n}\n```",
                "expected_output": '{"language":"typescript","overall_verdict":"request_changes","score":4,"findings":[{"severity":"high","description":"useEffect missing dependency array — infinite loop"},{"severity":"medium","description":"Missing key prop"}],"summary":"Infinite loop bug is critical."}',
                "scoring_criteria": "Must identify infinite loop (missing deps), key prop warning.",
            },
            {
                "input_text": "Review:\n```python\ndef process(items: list) -> list:\n    return [transform(x) for x in items if x is not None]\n```",
                "expected_output": '{"language":"python","overall_verdict":"approve","score":8,"findings":[{"severity":"info","description":"Generic type hint — consider list[Item]"}],"summary":"Clean, idiomatic Python."}',
                "scoring_criteria": "Should approve with high score. Should not flag false positives.",
            },
        ],
    },
    {
        "name": "Data Analyst — Statistical Reasoning",
        "description": "Tests statistical analysis, Python execution, and insight generation",
        "items": [
            {
                "input_text": "Analyze this data:\n```\nmonth,revenue,users\nJan,12000,450\nFeb,13500,480\nMar,11000,420\nApr,15000,520\nMay,16500,560\n```",
                "expected_output": '{"task":"Revenue trend analysis","key_metrics":{"avg_revenue":13600,"revenue_growth_pct":37.5},"insights":["Revenue grew 37.5% Jan-May","March dip interrupts trend"],"anomalies":["March dip"],"recommendations":["Investigate March dip"],"confidence":0.78}',
                "scoring_criteria": "Must compute growth rate, identify March anomaly, provide business recommendations.",
            },
            {
                "input_text": "Analyze A/B test:\n```\ngroup,conversions,total\ncontrol,234,1200\ntreatment,278,1180\n```",
                "expected_output": '{"task":"A/B test significance","key_metrics":{"control_rate":0.195,"treatment_rate":0.2356,"lift_pct":20.8,"p_value":0.032},"insights":["20.8% relative lift","p=0.032 < 0.05, statistically significant"],"recommendations":["Ship treatment variant"]}',
                "scoring_criteria": "Must run statistical test, compute lift (~20%), confirm significance, recommend shipping.",
            },
        ],
    },
    {
        "name": "Knowledge Curator — Entity Extraction",
        "description": "Tests entity/relationship extraction and knowledge gap identification",
        "items": [
            {
                "input_text": "Curate: 'Vector databases — Pinecone, Weaviate, Qdrant, pgvector'",
                "expected_output": '{"topic":"Vector databases","entities":[{"name":"Pinecone","type":"product"},{"name":"Qdrant","type":"product"},{"name":"pgvector","type":"extension"}],"relationships":[{"source":"pgvector","relation":"integrates_with","target":"PostgreSQL"}],"gaps":["Benchmark at 100M+ vectors"],"summary":"Mature market with clear segmentation."}',
                "scoring_criteria": "Must extract all 4 as entities, show relationships, identify meaningful gaps.",
            },
            {
                "input_text": "Curate: 'Model Context Protocol (MCP) by Anthropic'",
                "expected_output": '{"topic":"Model Context Protocol","entities":[{"name":"MCP","type":"protocol"},{"name":"MCP Server","type":"component"},{"name":"MCP Client","type":"component"}],"relationships":[{"source":"MCP Client","relation":"connects_to","target":"MCP Server"}],"gaps":["Security model for untrusted servers"],"summary":"Open protocol for LLM-tool standardization."}',
                "scoring_criteria": "Must identify MCP as protocol, its components, relationships, and practical gaps.",
            },
        ],
    },
    {
        "name": "Daily AI Briefing — Quality & Coverage",
        "description": "Tests briefing completeness, accuracy, and appropriate depth",
        "items": [
            {
                "input_text": "Generate today's AI briefing on language models and reasoning.",
                "expected_output": '{"papers":[{"title":"Example paper","one_liner":"...","why_it_matters":"..."}],"news":[{"headline":"...","source":"...","summary":"..."}],"signal_of_the_day":"Reasoning is the new benchmark battleground","trend_analysis":"Test-time compute is winning."}',
                "scoring_criteria": "Must include at least 2 papers, 2 news items, signal of the day, trend analysis.",
            },
            {
                "input_text": "AI briefing focused on agentic AI and tool use.",
                "expected_output": '{"papers":[{"title":"LangGraph paper","one_liner":"Graph-based agentic workflows","why_it_matters":"Used in production"}],"news":[{"headline":"OpenAI Operator","source":"OpenAI","summary":"Browser automation agent"}],"signal_of_the_day":"Reliability not capability is the bottleneck","trend_analysis":"Ecosystem consolidating around LangGraph patterns."}',
                "scoring_criteria": "Must cover agentic frameworks, real deployments. Signal must be practically relevant.",
            },
        ],
    },
]

router = APIRouter(prefix="/api/v1/golden-sets", tags=["golden-sets"])


# ── Schemas ──────────────────────────────────────────────────────────

class CreateSetBody(BaseModel):
    name: str
    description: str = ""


class CreateItemBody(BaseModel):
    input_text: str
    expected_output: str
    scoring_criteria: str = ""


class EvaluateBody(BaseModel):
    agent_id: UUID
    agent_version_label: str = ""


# ── Helpers ──────────────────────────────────────────────────────────

async def _get_workspace(repo: FlowRepository, user_id: UUID) -> UUID:
    ws = await repo.list_workspaces_for_user(user_id)
    if ws:
        return ws[0]["id"]
    # Fallback: return first workspace in DB (for dev/seeded environments)
    row = await repo._pool.fetchrow("SELECT id FROM workspaces LIMIT 1")
    if not row:
        raise HTTPException(status_code=404, detail="no workspace")
    return row["id"]


async def _assert_set_access(pool, set_id: UUID, workspace_id: UUID):
    row = await pool.fetchrow(
        "SELECT id FROM golden_sets WHERE id=$1 AND workspace_id=$2",
        set_id, workspace_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="golden set not found")


# ── Routes ───────────────────────────────────────────────────────────

@router.post("/seed-samples")
async def seed_sample_datasets(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Seed 5 sample golden datasets into the current user's workspace."""
    ws_id = await _get_workspace(repo, user_id)
    created = 0
    for sample in _SAMPLE_SETS:
        exists = await repo._pool.fetchval(
            "SELECT id FROM golden_sets WHERE workspace_id=$1 AND name=$2",
            ws_id, sample["name"],
        )
        if exists:
            continue
        set_id = await repo._pool.fetchval(
            "INSERT INTO golden_sets (workspace_id, name, description) VALUES ($1,$2,$3) RETURNING id",
            ws_id, sample["name"], sample["description"],
        )
        for item in sample["items"]:
            await repo._pool.execute(
                "INSERT INTO golden_items (set_id, input_text, expected_output, scoring_criteria) VALUES ($1,$2,$3,$4)",
                set_id, item["input_text"], item["expected_output"], item["scoring_criteria"],
            )
        created += 1
    return {"created": created, "skipped": len(_SAMPLE_SETS) - created}


@router.post("")
async def create_golden_set(
    body: CreateSetBody,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws_id = await _get_workspace(repo, user_id)
    sid = await repo._pool.fetchval(
        "INSERT INTO golden_sets (workspace_id, name, description) VALUES ($1,$2,$3) RETURNING id",
        ws_id, body.name.strip(), body.description.strip(),
    )
    return {"id": str(sid), "name": body.name.strip()}


@router.get("")
async def list_golden_sets(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws_id = await _get_workspace(repo, user_id)
    rows = await repo._pool.fetch(
        """
        SELECT gs.id, gs.name, gs.description, gs.created_at,
               COUNT(gi.id)::int AS item_count
        FROM golden_sets gs
        LEFT JOIN golden_items gi ON gi.set_id = gs.id
        WHERE gs.workspace_id = $1
        GROUP BY gs.id
        ORDER BY gs.created_at DESC
        """,
        ws_id,
    )
    return {
        "sets": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "description": r["description"],
                "item_count": r["item_count"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


@router.get("/{set_id}")
async def get_golden_set(
    set_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws_id = await _get_workspace(repo, user_id)
    await _assert_set_access(repo._pool, set_id, ws_id)
    items = await repo._pool.fetch(
        "SELECT id, input_text, expected_output, scoring_criteria, created_at FROM golden_items WHERE set_id=$1 ORDER BY created_at",
        set_id,
    )
    return {
        "items": [
            {
                "id": str(r["id"]),
                "input_text": r["input_text"],
                "expected_output": r["expected_output"],
                "scoring_criteria": r["scoring_criteria"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in items
        ]
    }


@router.post("/{set_id}/items")
async def add_golden_item(
    set_id: UUID,
    body: CreateItemBody,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws_id = await _get_workspace(repo, user_id)
    await _assert_set_access(repo._pool, set_id, ws_id)
    iid = await repo._pool.fetchval(
        """
        INSERT INTO golden_items (set_id, input_text, expected_output, scoring_criteria)
        VALUES ($1,$2,$3,$4) RETURNING id
        """,
        set_id, body.input_text.strip(), body.expected_output.strip(), body.scoring_criteria.strip(),
    )
    return {"id": str(iid)}


@router.delete("/{set_id}/items/{item_id}")
async def delete_golden_item(
    set_id: UUID,
    item_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    ws_id = await _get_workspace(repo, user_id)
    await _assert_set_access(repo._pool, set_id, ws_id)
    await repo._pool.execute("DELETE FROM golden_items WHERE id=$1 AND set_id=$2", item_id, set_id)
    return {"ok": True}


@router.get("/{set_id}/results")
async def get_results(
    set_id: UUID,
    agent_id: UUID | None = None,
    user_id: Annotated[UUID, Depends(get_current_user_id)] = None,
    repo: Annotated[FlowRepository, Depends(get_repo)] = None,
) -> dict:
    ws_id = await _get_workspace(repo, user_id)  # type: ignore
    await _assert_set_access(repo._pool, set_id, ws_id)  # type: ignore

    filter_sql = "AND gr.agent_id = $3" if agent_id else ""
    params = [set_id, ws_id] + ([agent_id] if agent_id else [])

    rows = await repo._pool.fetch(  # type: ignore
        f"""
        SELECT gr.id, gr.item_id, gr.agent_id, gr.agent_version_label,
               gr.score, gr.grading_rationale, gr.actual_output, gr.created_at,
               gi.input_text, gi.expected_output
        FROM golden_results gr
        JOIN golden_items gi ON gi.id = gr.item_id
        WHERE gi.set_id = $1 {filter_sql}
        ORDER BY gr.created_at DESC
        LIMIT 200
        """,
        *params,
    )

    items_rows = [{
        "id": str(r["id"]),
        "item_id": str(r["item_id"]),
        "agent_id": str(r["agent_id"]),
        "agent_version_label": r["agent_version_label"],
        "score": r["score"],
        "rationale": r["grading_rationale"],
        "actual_output": r["actual_output"],
        "input_text": r["input_text"],
        "expected_output": r["expected_output"],
        "created_at": r["created_at"].isoformat(),
    } for r in rows]

    scores = [r["score"] for r in rows if r["score"] is not None]
    return {
        "results": items_rows,
        "aggregate": {
            "count": len(scores),
            "avg_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
            "pass_rate": round(len([s for s in scores if s >= 0.7]) / len(scores), 3) if scores else 0.0,
            "min_score": round(min(scores), 3) if scores else 0.0,
        },
    }


@router.get("/{set_id}/history")
async def get_eval_history(
    set_id: UUID,
    agent_id: UUID | None = None,
    user_id: Annotated[UUID, Depends(get_current_user_id)] = None,
    repo: Annotated[FlowRepository, Depends(get_repo)] = None,
) -> dict:
    """Return daily aggregated eval scores for regression-over-time tracking."""
    ws_id = await _get_workspace(repo, user_id)  # type: ignore
    await _assert_set_access(repo._pool, set_id, ws_id)  # type: ignore

    filter_clause = "AND gr.agent_id = $2" if agent_id else ""
    params = [set_id] + ([agent_id] if agent_id else [])

    rows = await repo._pool.fetch(  # type: ignore
        f"""
        SELECT
            date_trunc('day', gr.created_at)::date  AS day,
            gr.agent_version_label                  AS version_label,
            gr.agent_id,
            COUNT(*)::int                            AS total,
            ROUND(AVG(gr.score)::numeric, 3)         AS avg_score,
            ROUND(
                COUNT(*) FILTER (WHERE gr.score >= 0.7)::numeric / COUNT(*),
                3
            )                                        AS pass_rate
        FROM golden_results gr
        JOIN golden_items gi ON gi.id = gr.item_id
        WHERE gi.set_id = $1
          AND gr.score IS NOT NULL
          {filter_clause}
        GROUP BY day, gr.agent_version_label, gr.agent_id
        ORDER BY day ASC, gr.agent_version_label
        """,
        *params,
    )

    return {
        "history": [
            {
                "day": str(r["day"]),
                "version_label": r["version_label"],
                "agent_id": str(r["agent_id"]),
                "total": r["total"],
                "avg_score": float(r["avg_score"]),
                "pass_rate": float(r["pass_rate"]),
            }
            for r in rows
        ]
    }


@router.post("/{set_id}/evaluate")
async def trigger_evaluate(
    set_id: UUID,
    body: EvaluateBody,
    background_tasks: BackgroundTasks,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    repo: Annotated[FlowRepository, Depends(get_repo)],
) -> dict:
    """Evaluate a golden set against an agent asynchronously."""
    ws_id = await _get_workspace(repo, user_id)
    await _assert_set_access(repo._pool, set_id, ws_id)

    async def _run():
        await evaluate_golden_set(
            repo._pool,
            set_id,
            body.agent_id,
            body.agent_version_label or None,
            workspace_id=ws_id,
            user_id=user_id,
        )

    background_tasks.add_task(_run)
    return {"status": "evaluating", "set_id": str(set_id), "agent_id": str(body.agent_id)}
