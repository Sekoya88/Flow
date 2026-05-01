# Flow

Agent platform: **FastAPI** (LangGraph deer-flow pipeline, asyncpg, JWT, SSE), **Redis + ARQ** for background execution jobs, **PostgreSQL + pgvector**, and **Next.js** (App Router, Tailwind v4, shadcn-style UI). Docker Compose for local dev.

## Monorepo layout

| Path | Role |
|------|------|
| `apps/web/` | Next.js frontend |
| `services/api/` | Python package `flow` — REST API, migrations (`migrations/`), Alembic (`alembic.ini`) |
| `docker-compose.yml` | `db`, `redis`, `qdrant`, `api`, `worker`, `web` |

## Where to run commands (important)

**`docker compose`** must run from the **repository root** (folder containing `docker-compose.yml`, `apps/`, `services/`).

Check: `ls docker-compose.yml apps/web services/api` lists all three.

---

## Quick start (Docker)

```bash
cd /path/to/Flow    # your clone root
cp .env.example .env
# optional: export FLOW_OPENAI_API_KEY=sk-... for real LLM runs

docker compose up --build
```

Minimum useful stack without the Next image:

```bash
docker compose up --build db redis qdrant api worker web
```

If you disable agentic RAG and omit Qdrant, you can still run `docker compose up --build db redis api worker web` and omit `FLOW_QDRANT_URL` / `FLOW_AGENTIC_RAG_ENABLED` on the API/worker (see `.env.example`).

### Published ports (host → container)

| Host | Service | Notes |
|------|---------|--------|
| **http://localhost:13000** | `web` → :3000 | UI (avoid clash with another app on **:3000**) |
| **http://localhost:18000**/docs | `api` → :8000 | OpenAPI |
| **localhost:55432** | `db` → Postgres :5432 | See [PostgreSQL](#postgresql-local-connection) |
| **localhost:16333** | `qdrant` → HTTP :6333 | Hybrid vector index for optional **agentic RAG** (`FLOW_QDRANT_URL`) |
| **localhost:16379** | `redis` → :6379 | Host port avoids clash if something else uses **:6379** |

Inside Compose, services talk on the Docker network: `postgresql://flow:flow@db:5432/flow`, `redis://redis:6379/0`, API/worker use `FLOW_QDRANT_URL=http://qdrant:6333` when agentic RAG is enabled.

### Agentic RAG (optional)

When **`FLOW_AGENTIC_RAG_ENABLED=true`** and **`FLOW_QDRANT_URL`** points at Qdrant (Compose sets both on `api`/`worker`), deer-flow **worker** retrieval uses a LangGraph pipeline (supervisor routing, Qdrant hybrid RRF + BM25 sparse, LLM grader, query rewrite, optional Tavily fallback). Knowledge ingest **dual-writes** chunks to Postgres and Qdrant. Audit rows land in **`rag_query_history`** / **`rag_citations`** (after migration `0003`). Without those env vars, retrieval stays **pgvector-only** as before.

Smoke from repo root with Compose up:

1. Set `FLOW_OPENAI_API_KEY`, optionally `FLOW_TAVILY_API_KEY`.
2. `docker compose up --build`
3. Add knowledge via API so chunks sync to Qdrant; run an execution with retrieve enabled.

Host URL when Qdrant is mapped on **16333**: `FLOW_QDRANT_URL=http://localhost:16333` (local API/worker against Compose Qdrant).

### Logs & LangSmith

- **`docker compose logs -f api worker`** — structlog console output with **`service=flow-api`** / **`service=flow-worker`** and agentic events (`agentic_rag.supervisor`, `agentic_rag.retrieve`, …). Compose enables **`FLOW_LOG_FORCE_COLORS=true`** so logs stay readable without a TTY.
- **LangSmith** (optional): in `.env` at repo root (Compose substitutes into containers):

```bash
FLOW_LANGSMITH_TRACING=true
FLOW_LANGSMITH_API_KEY=lsv2_pt_...   # from https://smith.langchain.com → Settings → API keys
FLOW_LANGSMITH_PROJECT=flow-local
# EU hosted Smith only:
# FLOW_LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
```

Restart `api` and `worker` after changing these. Traces cover LangChain/LangGraph calls (deer-flow + agentic RAG subgraph).

### Quick sanity checks

```bash
cd /path/to/Flow   # repo root
docker compose ps
curl -s http://localhost:18000/health
docker compose logs -f api worker   # expect lifespan.started, worker.started, then agentic_rag.* on runs
```

**Execution SSE:** the Run flow uses a short-lived `stream_jwt` query param where possible so the session JWT is not logged in URLs.

---

## PostgreSQL (local connection)

Credentials are fixed in `docker-compose.yml` for dev:

| Field | Value |
|-------|--------|
| Host | `localhost` (from your Mac/host), or hostname `db` from another container |
| Port | **55432** (mapped from container `5432`) |
| User | `flow` |
| Password | `flow` |
| Database | `flow` |

**Connection URL (tools on the host — TablePlus, DBeaver, `psql`):**

```text
postgresql://flow:flow@localhost:55432/flow
```

**CLI (`psql`)** — start DB first (`docker compose up -d db`):

```bash
psql "postgresql://flow:flow@localhost:55432/flow"
```

**From inside the Compose network** (e.g. one-off container): host is `db`, port `5432`:

```text
postgresql://flow:flow@db:5432/flow
```

**Migrations:** on API startup, Alembic runs `upgrade head`. Manual run from repo root:

```bash
( cd services/api && FLOW_DATABASE_URL=postgresql://flow:flow@localhost:55432/flow uv run alembic upgrade head )
```

Alembic uses **psycopg v3** (`postgresql+psycopg://`); bare `postgresql://` URLs are normalized in `migrations/env.py`.

---

## Worker (`arq`)

The `worker` service runs **ARQ** jobs (e.g. `run_deer_execution`). For queued runs to complete, **`worker` must be up** alongside `api`, `db`, and `redis`.

---

## Dev without Docker (API + Next on the host)

Keep Postgres (and optionally Redis) in Docker:

```bash
docker compose up -d db redis
export FLOW_DATABASE_URL=postgresql://flow:flow@localhost:55432/flow
export FLOW_REDIS_URL=redis://localhost:16379/0
export FLOW_JWT_SECRET=$(openssl rand -hex 32)
cd services/api && uv sync --extra dev && uv run uvicorn flow.interfaces.http.main:app --reload --host 0.0.0.0 --port 8000
```

If Redis is mapped on **16379** (default in this repo), use `FLOW_REDIS_URL` as above. If you use a local Redis on **6379**, use `redis://localhost:6379/0`.

Second terminal (from repo root):

```bash
cd apps/web && npm install && npm run dev
```

Next → **http://localhost:3000**. Point the web app at the API via `apps/web/.env.local`:

- API in Docker on the host: `NEXT_PUBLIC_FLOW_API_URL=http://localhost:18000`
- Local uvicorn only: `NEXT_PUBLIC_FLOW_API_URL=http://localhost:8000`

Set `FLOW_CORS_ORIGINS` to include `http://localhost:3000` (and `http://localhost:13000` if needed).

---

## Optional: tests + web build before full compose

From **repository root**:

```bash
docker compose up -d db
( cd services/api && uv sync --extra dev && uv run python -m pytest tests/ -q )
( cd apps/web && npm ci && npm run build )
docker compose up --build
```

---

## API image only

```bash
docker build -t flow-api -f services/api/Dockerfile services/api
```

## License

MIT
