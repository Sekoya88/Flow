# Flow API

FastAPI service for the Flow monorepo. Package: `flow`.

```bash
# From repo root, with Postgres/Redis up:
cd services/api && uv sync --extra dev
uv run uvicorn flow.interfaces.http.main:app --reload --port 8000
uv run arq flow.infrastructure.queue.worker.WorkerSettings
```

- **OpenAPI:** `http://localhost:18000/docs` (Docker) or `:8000` (local uvicorn)
- **Migrations:** `uv run alembic upgrade head` (also on API startup)
- **Tests:** `uv run pytest tests/ -v`

See [README.md](../../README.md) and [docs/soa.md](../../docs/soa.md) for full platform overview.
