# Flow

Personal second brain and agent platform. Upload documents, ask questions, get cited answers. Agents improve themselves automatically through evaluation, prompt rewriting, and A/B testing.

Built on **FastAPI** (LangGraph pipeline, asyncpg, JWT, SSE), **Redis + ARQ** for background jobs, **PostgreSQL + pgvector**, and **Next.js** (App Router, Tailwind v4).

## What you can do today

- **Upload documents** — PDF, .docx, .md, .txt up to 20 MB
- **Crawl URLs** — paste a web page, Flow extracts and indexes the main content
- **Ask questions** — streamed answers with inline `[1]` `[2]` citation markers
- **See sources** — click any citation to expand the exact chunk from your document
- **Feedback loop** — 👍/👎 on answers; negative feedback improves future retrievals
- **Agent versioning** — every config change snapshots a new genome version (CANDIDATE → ACTIVE → ARCHIVED)
- **Evaluation loop** — golden sets + LLM judge + automatic prompt rewriting + A/B testing
- **Agent schedules** — run agents on a cron schedule and deliver results via configurable channels
- **Onboarding wizard** — guided first-run that gets you from signup to first answer in under 2 minutes

---

## Monorepo layout

| Path | Role |
|------|------|
| `apps/web/` | Next.js frontend |
| `services/api/` | Python package `flow` — REST API, LangGraph agents, migrations |
| `docker-compose.yml` | `db`, `redis`, `qdrant`, `api`, `worker`, `web` |

---

## Quick start (Docker)

```bash
cd /path/to/Flow
cp .env.example .env
# Add your OpenAI key for embeddings + LLM answers:
# FLOW_OPENAI_API_KEY=sk-...
docker compose up --build
```

| Host URL | Service |
| -------- | ------- |
| **<http://localhost:13000>** | UI |
| **<http://localhost:18000/docs>** | API (OpenAPI) |
| `localhost:55432` | Postgres |
| `localhost:16379` | Redis |
| `localhost:16333` | Qdrant (optional agentic RAG) |

---

## First run walkthrough

1. Open **<http://localhost:13000>** → register
2. Onboarding wizard: choose **"Ask questions about my documents"** → upload a PDF
3. Go to **Run** → type a question → get a streamed answer with cited sources
4. Click a `[1]` citation → see the exact document chunk the answer came from
5. Rate the answer → low scores feed back into the retrieval grader

---

## Knowledge ingestion

### Via the UI (`/knowledge`)

- **Upload file** — drag/click to pick PDF, .md, .txt, .docx (max 20 MB)
- **Add from URL** — paste any `https://` URL, Flow strips nav/footer and indexes the article body
- **Add from text** — paste raw markdown or plain text directly

### Via the API

```bash
# File upload
curl -X POST http://localhost:18000/api/v1/knowledge/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "workspace_id=$WID" \
  -F "file=@/path/to/doc.pdf"

# URL crawl
curl -X POST http://localhost:18000/api/v1/knowledge/crawl \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"workspace_id\": \"$WID\", \"url\": \"https://example.com/article\"}"
```

Both return `{ "id": "<source_id>", "title": "..." }`. The source appears immediately in the sources list; chunk count updates as embedding finishes.

---

## Running agents (`/run`)

Select an agent, type a message, hit **Run**. The LangGraph pipeline streams:

```text
planner → worker (RAG + memory) → synthesizer → citations SSE event
```

Worker retrieves up to 8 knowledge chunks (pgvector cosine), numbers them `[1]…[N]`, and instructs the LLM to cite inline. Synthesizer emits a `citations` SSE frame that the frontend uses to render the **Sources** panel below the answer.

**Tools per agent** (configurable in Run page):

| Tool | Effect |
| ---- | ------ |
| Knowledge search | pgvector retrieval (+ Qdrant when agentic RAG enabled) |
| Long-term memory | Recall past run summaries via `AsyncPostgresStore` |
| Sandbox | Execute Python code blocks |

---

## Agent Genome (versioning)

Every agent has a **genome** — a versioned snapshot of its full configuration:

| Field | What it captures |
| ----- | ---------------- |
| `template` | LangGraph graph template (`react-agent`, `deer_flow`, …) |
| `system_prompt` | The agent's instruction prompt |
| `llm_config` | Provider, model, temperature |
| `tools` | Which tools are enabled (`{"retrieve": true, "sandbox": false, ...}`) |
| `skills` | Skill instructions embedded in the prompt |

**Version lifecycle:** `CANDIDATE` → `ACTIVE` → `ARCHIVED`

- Versions snapshot automatically on config changes, eval passes, or prompt rewrites
- Only one version is `ACTIVE` at a time per agent
- Approving a proposal promotes a `CANDIDATE` to `ACTIVE` and archives the previous one
- Full version history available in the UI (`/agents/:id/versions`)

---

## Continuous Improvement Loop

A nightly ARQ cron job (`auto_eval_tick`, 03:00 UTC) closes the self-improvement loop:

```text
1. Run golden set evaluation (LLM judge, 0.0–1.0 per item)
2. If pass_rate < 0.7 → extract failed items → Prompt Rewriter
3. Prompt Rewriter (GPT-4o-mini) analyzes failures → proposes targeted prompt edits
4. If confidence ≥ 0.3 and prompt changed → snapshot as CANDIDATE genome
5. If active baseline exists → run A/B test on same golden set
6. If candidate wins → create Proposal for human approval
7. Human approves → CANDIDATE promoted to ACTIVE, previous version ARCHIVED
```

**Prompt Rewriter** (`flow/application/prompt_rewriter.py`):

- Takes current system prompt + failed golden items (input, expected, actual, judge rationale)
- Produces improved prompt with structured changelog and confidence score (0.0–1.0)
- Skips rewrites below 0.3 confidence or when prompt is unchanged
- Original prompt always restored after snapshotting candidate (crash-safe `try/finally`)

**A/B Test Runner** (`flow/application/ab_runner.py`):

- Runs both genome versions against the same golden set
- Determines winner by average score delta
- Only creates promotion proposal when candidate significantly outperforms baseline

---

## Golden Sets & Evaluation (`/evals`)

**Golden Sets** are curated test cases (input → expected output) used to measure agent quality.

- Create via UI or seed with `scripts/seed_agents_and_datasets.py`
- Run evaluations manually or let `auto_eval_tick` trigger them nightly
- Results accumulated in `golden_results` rows, grouped by `eval_run_id`
- LLM judge uses `gpt-4o-mini`: `{"score": 0.0–1.0, "rationale": "…"}`

---

## Agent Schedules

Agents can run on a schedule:

- Configure `cron_expr` (e.g. `0 8 * * *` = daily at 8 AM)
- Set `prompt_template` for the scheduled run
- Set `delivery_type` / `delivery_target` for result routing
- Schedules stored in `agent_schedules`, executed by the ARQ worker

---

## Observability

**FlowCallbackHandler** (`flow/infrastructure/observability/callbacks.py`) instruments every LangGraph execution:

- Attaches `workspace_id`, `agent_id`, `execution_id`, `template` to all log events
- Tracks per-call latency (ms) for LLM calls and tool invocations
- Emits structured `structlog` events: `llm.start`, `llm.end`, `tool.start`, `tool.end`, `chain.error`
- Integrates with LangSmith tracing (`FLOW_LANGSMITH_API_KEY`)

Docker containers emit JSON logs (`FLOW_LOG_JSON=true`). Cron job failures logged with `exc_type`, `workspace_id`, `agent_id` fields for structured querying.

---

## Feedback loop

After each run, rate the answer (slider 0–100%). Scores below 50% automatically insert an **agent negative** — a record of the query that produced a poor result. The worker grader uses top-5 negatives as few-shot examples to avoid repeating similar bad retrievals.

---

## PostgreSQL (local connection)

```text
postgresql://flow:flow@localhost:55432/flow
```

Migrations run automatically on API startup via Alembic. 12 migrations (`0001_initial_schema` → `0012_agent_schedules`).

---

## Dev without Docker

```bash
# Keep DB + Redis + Qdrant in Docker
docker compose up -d db redis qdrant

export FLOW_DATABASE_URL=postgresql://flow:flow@localhost:55432/flow
export FLOW_REDIS_URL=redis://localhost:16379/0
export FLOW_JWT_SECRET=$(openssl rand -hex 32)
export FLOW_OPENAI_API_KEY=sk-...

cd services/api && uv sync --extra dev
uv run uvicorn flow.interfaces.http.main:app --reload --port 8000

# Second terminal
cd apps/web && npm install && npm run dev
# → http://localhost:3000
# Set apps/web/.env.local: NEXT_PUBLIC_FLOW_API_URL=http://localhost:8000
```

---

## Agentic RAG (optional)

When `FLOW_AGENTIC_RAG_ENABLED=true` and `FLOW_QDRANT_URL` is set, retrieval uses a LangGraph sub-pipeline (supervisor routing, Qdrant hybrid RRF + BM25, LLM grader, query rewrite, optional Tavily fallback). Knowledge ingest dual-writes to Postgres and Qdrant. Without these env vars, retrieval falls back to pgvector-only.

---

## Tests

```bash
# Unit + offline tests (no DB needed)
cd services/api && uv run pytest tests/ -v --ignore=tests/test_health.py

# Full suite (requires Postgres on 55432)
docker compose up -d db && uv run pytest tests/ -v
```

---

## License

MIT
