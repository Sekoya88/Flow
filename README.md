# Flow

Agent platform: **FastAPI** (LangGraph deer-flow pipeline, asyncpg, JWT, SSE), **Redis + ARQ** for background execution jobs, **PostgreSQL + pgvector**, and **Next.js** (App Router, Tailwind v4, shadcn-style UI). Docker Compose for local dev.

## Monorepo layout

| Path | Role |
|------|------|
| `apps/web/` | Next.js frontend |
| `services/api/` | Python package `flow` — REST API, migrations (`migrations/`), Alembic (`alembic.ini`) |
| `docker-compose.yml` | `db`, `redis`, `api`, `worker`, `web` |

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
docker compose up --build db redis api worker web
```

### Published ports (host → container)

| Host | Service | Notes |
|------|---------|--------|
| **http://localhost:13000** | `web` → :3000 | UI (avoid clash with another app on **:3000**) |
| **http://localhost:18000**/docs | `api` → :8000 | OpenAPI |
| **localhost:55432** | `db` → Postgres :5432 | See [PostgreSQL](#postgresql-local-connection) |
| **localhost:16379** | `redis` → :6379 | Host port avoids clash if something else uses **:6379** |

Inside Compose, services talk on the Docker network: `postgresql://flow:flow@db:5432/flow`, `redis://redis:6379/0`.

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
