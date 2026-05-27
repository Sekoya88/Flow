# Flow

Personal AI second brain and agent platform. Ingest documents, run streamed agents with RAG + memory, track research papers, and query a knowledge graph — all self-hosted.

Built on **FastAPI** (LangGraph, asyncpg, JWT, SSE), **Redis + ARQ**, **PostgreSQL + pgvector**, **Qdrant** (optional hybrid RAG), and **Next.js 16** (App Router, Tailwind v4).

---

## Apps

| App | Path | Description |
| --- | ---- | ----------- |
| **Web** | `apps/web/` | Next.js frontend — agents, knowledge, research, graph |
| **FlowIsland** | `apps/mac/FlowIsland/` | macOS Dynamic Island / notch client (Swift) |
| **Chrome Extension** | `apps/chrome-extension/` | Browser sidebar — clip pages, run agents, research digest |

---

## Quick start (Docker)

```bash
cp .env.example .env
# Edit .env — minimum required:
# FLOW_OPENAI_API_KEY=sk-...
# FLOW_JWT_SECRET=$(openssl rand -hex 32)

docker compose up --build
```

| URL | Service |
| --- | ------- |
| <http://localhost:13000> | Web UI |
| <http://localhost:18000/docs> | API (OpenAPI) |
| <http://localhost:16333> | Qdrant dashboard |

After first boot: open <http://localhost:13000> → register → complete onboarding.

> See [experience.md](./experience.md) for full setup guide including FlowIsland and the Chrome extension.

---

## Capabilities

| Area | What it does |
| ---- | ------------ |
| **Knowledge** | Upload PDF/DOCX/MD/TXT, crawl URLs — RAG with `[1]` `[2]` citations |
| **Agents** | Create agents, genome versions, golden sets, A/B tests, auto-improve loop |
| **Research Digest** | Daily arXiv + HuggingFace papers, AI-scored, exportable to Obsidian |
| **Graph** | Knowledge graph of agents, skills, papers — queryable via natural language |
| **Skills** | Reusable skill instructions per agent, versioned, in-browser playground, auto-trainable via ReflACT |
| **Memory** | Long-term facts via `AsyncPostgresStore`, visible at `/memory` |
| **Evals** | Golden set runs + LLM judge + nightly prompt rewriting |
| **Agentic RAG** | Qdrant hybrid search (BM25 + dense) fused via RRF when enabled |

---

## Skill Training — ReflACT optimizer (SkillOpt)

Flow implements Microsoft's [SkillOpt](https://arxiv.org/abs/2605.23904) **ReflACT** pipeline: a text-space optimizer that trains skill documents (markdown prompts) via bounded structured edits, without touching model weights. Inspired by gradient descent but operating on text — each epoch proposes patches, ranks them by impact, applies within a budget, and validates via golden-set eval before accepting.

### How it works

```text
ROLLOUT  → run agent on golden items, collect failures
REFLECT  → LLM analyzes failures → structured patches [{op, target, content, impact_score}]
AGGREGATE → merge patches targeting the same section heading (keep highest impact)
SELECT   → rank by impact_score DESC, cap at edit_budget (the "learning rate")
UPDATE   → apply bounded text edits anchored to ## SectionName headings
EVALUATE → validate: accept if eval_score > baseline + 0.02, else reject + buffer the failed edits
```

Rejected edits are buffered cross-epoch — the LLM won't re-propose them in future runs.

### Enable training on a skill

Via API:

```bash
# Enable nightly auto-training (runs every day at 05:00 UTC)
curl -X PATCH http://localhost:18000/api/v1/skills/{skill_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"training_mode": "react"}'

# Trigger a manual training run immediately
curl -X POST http://localhost:18000/api/v1/skills/{skill_id}/train \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "...", "workspace_id": "...", "edit_budget": 5, "max_epochs": 3}'
# → {"run_id": "uuid"}

# Poll status
curl http://localhost:18000/api/v1/skills/{skill_id}/training-runs/{run_id} \
  -H "Authorization: Bearer $TOKEN"
```

### View training in the UI

Navigate to **Agents → [Your Agent] → Skills → Training** (`/agents/{id}/skills/training`).

The training panel shows:

- **Toggle** — enable/disable nightly `react` auto-training per skill
- **Train Now** — trigger an immediate run (disabled while a run is active)
- **Epoch timeline** — each epoch shows eval score, baseline score, improvement delta, patch count, and accept/reject status
- **Run history** — all past runs with status badges (pending / running / done / failed)

Training results also appear in the **Knowledge Graph** as `improved_by` edges between skill versions, and trigger a new **genome snapshot** with `trigger=skill_train`.

### Test it

```bash
cd services/api

# Unit tests — each ReflACT stage isolated
.venv/bin/pytest tests/test_skill_trainer.py -v

# Repo integration tests — training run CRUD
.venv/bin/pytest tests/test_repo_training.py -v

# API route tests
.venv/bin/pytest tests/test_routes_skill_training.py tests/test_patch_skill.py -v

# Worker task tests
.venv/bin/pytest tests/test_worker_training.py -v

# Full suite
.venv/bin/pytest tests/ -v   # 38 skill-training tests + all others
```

### Database tables added

| Table | Purpose |
| ----- | ------- |
| `skill_training_runs` | One row per training run (multi-epoch), tracks status, scores, edit budget |
| `skill_raw_patches` | Individual patch proposals from each Reflect stage; rejected ones buffered |
| `skill_training_epochs` | Per-epoch results: candidate skill, eval score, acceptance decision |

Migration: `services/api/migrations/versions/0031_skillopt.py`

---

## Monorepo layout

```text
apps/
  web/                 Next.js frontend
  mac/FlowIsland/      macOS notch app (Swift/SwiftUI)
  chrome-extension/    Browser extension (React/Vite)
services/
  api/                 FastAPI + LangGraph + ARQ worker
  mcp/                 MCP server (Claude integration)
docker-compose.yml     db · redis · qdrant · api · worker · web
Makefile               build · update · migrate · rebuild
```

---

## Makefile

| Target | Effect |
| ------ | ------ |
| `make up` | `docker compose up -d` |
| `make build` | Build images + migrate + seed |
| `make update` | Rebuild api/worker/web + migrate + seed — **preserves DB** |
| `make rebuild` | Full wipe + no-cache build |
| `make migrate` | Run Alembic migrations only |
| `make logs` | Follow all service logs |

---

## Dev without Docker

```bash
# Infra only
docker compose up -d db redis qdrant

# API
export FLOW_DATABASE_URL=postgresql://flow:flow@localhost:55432/flow
export FLOW_REDIS_URL=redis://localhost:16379/0
export FLOW_JWT_SECRET=$(openssl rand -hex 32)
export FLOW_OPENAI_API_KEY=sk-...
cd services/api && uv sync --extra dev
uv run uvicorn flow.interfaces.http.main:app --reload --port 8000

# Worker (second terminal)
uv run arq flow.infrastructure.queue.worker.WorkerSettings

# Web
cd apps/web
echo "NEXT_PUBLIC_FLOW_API_URL=http://localhost:8000" > .env.local
npm install && npm run dev   # → http://localhost:3000
```

---

## Tests

```bash
cd services/api && uv run pytest tests/ -v
cd apps/web && npm test
```

---

## MCP — Connect Claude / Cursor / Windsurf to Flow

Flow exposes a [Model Context Protocol](https://modelcontextprotocol.io) server with **33 tools** covering agents, knowledge, research digest, skills, memory, and the knowledge graph.

Transports: **SSE** (`/sse`) and **Streamable HTTP** (`/mcp`) — both on port `18001`.

### 1. Start the stack

```bash
docker compose up -d   # MCP server starts automatically on port 18001
curl http://localhost:18001/health
# → {"status":"ok","service":"flow-mcp"}
```

### 2. Get a JWT token

```bash
FLOW_EMAIL=you@example.com FLOW_PASSWORD=secret bash scripts/get-flow-token.sh
```

The script prints ready-to-paste config snippets for every client.

> Manual: `curl -s -X POST http://localhost:18000/api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"...","password":"..."}' | jq -r .access_token`

### 3. Connect your client

**Claude Desktop** — `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "flow": {
      "url": "http://localhost:18001/sse?token=<YOUR_JWT>"
    }
  }
}
```

**Claude Code** (CLI) — `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "flow": {
      "type": "sse",
      "url": "http://localhost:18001/sse?token=<YOUR_JWT>"
    }
  }
}
```

**Cursor** — `.cursor/mcp.json` (already present in this repo, update the token):

```json
{
  "mcpServers": {
    "flow": {
      "url": "http://localhost:18001/sse?token=<YOUR_JWT>"
    }
  }
}
```

**Windsurf / clients supporting Streamable HTTP**:

```text
http://localhost:18001/mcp?token=<YOUR_JWT>
```

### 4. Available tools

| Category | Tools |
| -------- | ----- |
| **Agents** | `flow_run_agent`, `flow_get_execution`, `flow_list_agents` |
| **Skills** | `flow_create_skill`, `flow_patch_skill`, `flow_list_skills` |
| **Knowledge** | `flow_ingest_knowledge`, `flow_search_knowledge` |
| **Memory** | `flow_memory_write`, `flow_memory_read` |
| **Knowledge Graph** | `flow_kg_query`, `flow_kg_add_node` |
| **Workspace** | `flow_workspace_snapshot`, `flow_list_executions`, `flow_get_thread`, `flow_list_schedules` |
| **Research Digest** | `flow_digest_papers`, `flow_trigger_digest`, `flow_get_digest_config` |
| **GitHub** | `github_trigger_workflow`, `github_get_run_status`, `github_list_recent_runs`, `github_get_run_logs` |
| **Obsidian** | `obsidian_create_note`, `obsidian_append_note`, `obsidian_read_note`, `obsidian_list_notes` |
| **Research** | `arxiv_search`, `arxiv_fetch_abstract`, `hf_search_papers`, `hf_get_paper_details` |
| **Web** | `web_crawl_article`, `web_search_tavily` |

Start with `flow_workspace_snapshot` to orient yourself — it returns all agents, recent executions, and cron jobs in one call.

### 5. Resources

| URI | Contents |
| --- | -------- |
| `flow://workspace` | Full workspace JSON: agents, skills count, recent executions |
| `flow://agents` | Active agents list (JSON) |
| `flow://skills` | Skill catalog with scores |

---

## License

MIT
