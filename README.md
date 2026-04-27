# Flow

Agent platform: **clean layered Python** (FastAPI + LangGraph + asyncpg) and **Next.js + shadcn**. Docker Compose for local dev; Railway-ready.

## Where to run commands (important)

**`docker compose`** reads `docker-compose.yml` in the **current working directory**. You must be in the **repository root** — the folder that directly contains:

- `docker-compose.yml`
- `apps/`
- `services/`

If your shell is elsewhere (e.g. `~/Documents`, `services/api`, or `apps/web`), then:

- `cd services/api` fails → there is no `services/api` *inside* those folders.
- `cd apps/web` fails → same reason.

**Check:** `ls docker-compose.yml apps/web services/api` should list all three without errors.

**Fix:** `cd` to your clone root first, e.g. `cd ~/Documents/workspace/Flow` (adjust to your path).

---

## Quick start (Docker: DB + API + Web)

```bash
# 1) From repository root only
cp .env.example .env
# optional: export FLOW_OPENAI_API_KEY=... for real LLM runs

docker compose up --build
```

**Published ports on your machine (host → container):**

| Host (your browser / curl) | Inside stack | Notes |
|----------------------------|----------------|-------|
| http://localhost:**13000** | web :3000 | UI — host **13000** avoids another app using **3000** |
| http://localhost:**18000**/docs | api :8000 | OpenAPI — host **18000** avoids another app using **8000** |
| `localhost:55432` | Postgres :5432 | Same as `FLOW_DATABASE_URL` in `.env.example` for tools on the host |

Open **`/`** for the marketing home (layout mirrors **lucis-agent** — grain, gradient, sticky header, `max-w-3xl` column). With a JWT in `localStorage`, `/` redirects to `/dashboard`. Register at `/register`, then use the app.

**Execution SSE:** the Run page calls `POST /api/v1/executions/{id}/stream-token` for a short-lived `stream_jwt`, then connects with `?stream_jwt=` so the long-lived session JWT is not in the query string. The API still accepts legacy `?access_token=` for debugging.

---

## Optional: tests + web build before full compose

Still from **repository root**. Parentheses run each line in a subshell so you never “stay” stuck inside `services/api` for the next command:

```bash
docker compose up -d db
( cd services/api && uv sync --extra dev && uv run python -m pytest tests/ -q )
( cd apps/web && npm ci && npm run build )
docker compose up --build
```

If you **prefer** separate `cd` lines without subshells, run `cd services/api`, do your work, then **`cd` back to the repo root** before `cd apps/web` (e.g. `cd ../..` from `services/api` only works if your layout is `Flow/services/api` — two levels up to `Flow`).

---

## Dev without Docker (API + Next on the host)

From **repository root**:

```bash
docker compose up -d db
export FLOW_DATABASE_URL=postgresql://flow:flow@localhost:55432/flow
export FLOW_JWT_SECRET=$(openssl rand -hex 32)
cd services/api && uv sync --extra dev && uv run uvicorn flow.interfaces.http.main:app --reload --host 0.0.0.0 --port 8000
```

In **another** terminal, from **repository root**:

```bash
cd apps/web && npm install && npm run dev
```

Next defaults to **http://localhost:3000**; point it at the API with `apps/web/.env.local`:

- **Docker Compose** (API on host **:18000**): `NEXT_PUBLIC_FLOW_API_URL=http://localhost:18000` (also the in-code default when unset).
- **Local uvicorn** only: `NEXT_PUBLIC_FLOW_API_URL=http://localhost:8000`

Ensure the API allows that origin, e.g. `FLOW_CORS_ORIGINS=http://localhost:3000` (see `.env.example`).

---

## Monorepo layout

```
apps/web/           # Next.js frontend
services/api/       # FastAPI + flow package
docs/superpowers/plans/
```

Docker image for API only (from repo root):

```bash
docker build -t flow-api -f services/api/Dockerfile services/api
```

## License

MIT
