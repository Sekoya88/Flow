.PHONY: up down build rebuild seed logs restart dev

# ── Full rebuild + start ──────────────────────────────────────────────────────
rebuild:
	docker compose down -v --remove-orphans
	docker compose build --no-cache
	docker compose up -d
	@echo "\n✓ Stack rebuilt. Waiting for DB..."
	@sleep 5
	docker compose exec api uv run alembic upgrade head
	docker compose exec api uv run python scripts/seed_agents_and_datasets.py
	docker compose exec api uv run python scripts/seed_skills.py
	@echo "\n✓ Ready → http://localhost:13000"

# ── Normal start (no rebuild) ─────────────────────────────────────────────────
up:
	docker compose up -d

# ── Quick rebuild (uses cache, KEEPS volumes/data) ────────────────────────────
build:
	docker compose up --build -d
	@sleep 5
	docker compose exec api uv run alembic upgrade head
	docker compose exec api uv run python scripts/seed_agents_and_datasets.py
	docker compose exec api uv run python scripts/seed_skills.py
	@echo "\n✓ Ready → http://localhost:13000"

# ── Apply migrations + restart services WITHOUT wiping volumes ────────────────
# Use this for code changes + new migrations. NEVER destroys the DB.
update:
	docker compose up --build -d api worker web
	@sleep 4
	docker compose exec api uv run alembic upgrade head
	@echo "\n✓ Updated (data preserved) → http://localhost:13000"

# ── Stop everything ───────────────────────────────────────────────────────────
down:
	docker compose down --remove-orphans

# ── Seed only (agents + golden sets) ─────────────────────────────────────────
seed:
	docker compose exec api uv run python scripts/seed_agents_and_datasets.py

# ── Migrations only ───────────────────────────────────────────────────────────
migrate:
	docker compose exec api uv run alembic upgrade head

# ── Logs ─────────────────────────────────────────────────────────────────────
logs:
	docker compose logs -f --tail=100

logs-api:
	docker compose logs -f api --tail=100

logs-worker:
	docker compose logs -f worker --tail=100

# ── Restart a single service ──────────────────────────────────────────────────
restart:
	docker compose restart api worker

# ── Local dev (no docker) ─────────────────────────────────────────────────────
dev:
	@echo "Start these in separate terminals:"
	@echo "  cd services/api && uv run uvicorn flow.interfaces.http.main:app --reload --port 8000"
	@echo "  cd services/api && uv run arq flow.infrastructure.queue.worker.WorkerSettings"
	@echo "  cd apps/web     && npm run dev"
