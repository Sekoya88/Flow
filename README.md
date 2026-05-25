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
| **Skills** | Reusable skill instructions per agent, versioned, in-browser playground |
| **Memory** | Long-term facts via `AsyncPostgresStore`, visible at `/memory` |
| **Evals** | Golden set runs + LLM judge + nightly prompt rewriting |
| **Agentic RAG** | Qdrant hybrid search (BM25 + dense) fused via RRF when enabled |

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
