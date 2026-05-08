# Flow

Personal second brain and agent platform. Upload PDFs and documents, ask questions, get cited answers. Built on **FastAPI** (LangGraph pipeline, asyncpg, JWT, SSE), **Redis + ARQ** for background jobs, **PostgreSQL + pgvector**, and **Next.js** (App Router, Tailwind v4).

## What you can do today

- **Upload documents** — PDF, .docx, .md, .txt up to 20 MB
- **Crawl URLs** — paste a web page, Flow extracts and indexes the main content
- **Ask questions** — streamed answers with inline `[1]` `[2]` citation markers
- **See sources** — click any citation to expand the exact chunk from your document
- **Feedback loop** — 👍/👎 on answers; negative feedback improves future retrievals
- **Agent Metacognition** — LLM-based reflection and confidence scoring
- **Evaluation Loop** — Golden Sets and automated A/B testing for agent variations
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
| Knowledge search | Enable pgvector retrieval |
| Long-term memory | Recall past run summaries |
| Sandbox | Execute Python code blocks |

---

## Agentic Evolution (Metacognition)

Flow is designed as a continuously improving agentic framework. 

### 1. Skills & Versioning
Agents hold **Skills** (`SKILL.md`), which are granular sets of instructions, behaviors, and knowledge boundaries. Both Skills and overall Agent Configurations are versioned. You can:
- Edit Skills using a markdown/YAML editor.
- View LCS-based side-by-side diffs.
- Restore previous snapshots of your agent if performance degrades.

### 2. Golden Sets & Evaluation
To prevent regressions, Flow supports **Golden Sets** (curated inputs and expected outputs).
- **Run Evaluations**: A Background task runs the Golden Set items through your agent.
- **LLM-Judge**: Uses `gpt-4o-mini` to score factual accuracy and alignment on a 0.0-1.0 scale with a grading rationale.
- **Auto-refinement**: If an evaluation fails (score < 0.7), the system automatically drafts an improvement Proposal (e.g. "Add a skill for handling unstructured queries") that you can approve.

### 3. A/B Testing
Compare two agents head-to-head on the same Golden Set to validate prompt modifications or different routing configurations.

---

## Feedback loop

After each run, rate the answer (slider 0–100%). Scores below 50% automatically insert an **agent negative** — a record of the query that produced a poor result. The worker grader uses top-5 negatives as few-shot examples to avoid repeating similar bad retrievals.

You can view the agent's historical confidence in a sparkline chart on the Dashboard and click any data point to drill down into the specific execution context.

---

## PostgreSQL (local connection)

```text
postgresql://flow:flow@localhost:55432/flow
```

Migrations run automatically on API startup via Alembic.

---

## Dev without Docker

```bash
# Keep DB + Redis in Docker
docker compose up -d db redis

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
