# Flow on Railway

Two services: **Postgres** (Railway plugin or Neon) + **API** (`services/api`) + **Web** (`apps/web`). Compose is the source of truth for env names.

## API service

- **Root directory:** `services/api`
- **Dockerfile:** `Dockerfile` (default)
- **Start:** `uv run uvicorn flow.interfaces.http.main:app --host 0.0.0.0 --port $PORT`

Set variables (production):

| Variable | Notes |
|----------|--------|
| `FLOW_DATABASE_URL` | Postgres connection string (must include `postgresql://` and reach DB from Railway network) |
| `FLOW_JWT_SECRET` | `openssl rand -hex 32` |
| `FLOW_OPENAI_API_KEY` | Optional; required for LLM + embeddings |
| `FLOW_CORS_ORIGINS` | Comma-separated origins, e.g. `https://your-web.up.railway.app` |
| `FLOW_LOG_JSON` | `true` in prod |

## Web service

- **Root directory:** `apps/web`
- **Build argument:** `NEXT_PUBLIC_FLOW_API_URL` = public URL of the API (e.g. `https://your-api.up.railway.app`)

Runtime:

| Variable | Notes |
|----------|--------|
| `NEXT_PUBLIC_FLOW_API_URL` | Same as build arg; used by the browser |

## Local parity

- Postgres on host port **55432** (see root `docker-compose.yml`) avoids conflicts with a local `5432` server.
- Compose publishes **web** on host **13000** (→ container 3000) and **API** on host **18000** (→ container 8000) to reduce clashes with common dev ports **3000** / **8000**.
- After changing DB port, update `FLOW_DATABASE_URL` in `.env`.

## Health

- API: `GET /health` (JSON `db: true|false`)
- Web: Next.js responds on `/`
