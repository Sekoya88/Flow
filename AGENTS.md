## Learned User Preferences

- For substantial Flow planning work, prefer GSD-style phased output: goals, non-goals, dependencies between phases, concrete file areas (`apps/web/...`, `services/api/...`), shadcn CLI add hints where useful, testable acceptance criteria, risks and mitigations, and quick wins vs multi-day work.
- When the user asks for planning or product copy in French, use French for that deliverable. Operational and debug conversations default to French too.
- Explain and document `docker compose`, `uv`/`pytest` under `services/api`, and `npm` under `apps/web` as run from the **Flow repository root** (the directory that contains `docker-compose.yml`, `apps/`, and `services/`) so relative `cd` steps do not fail.
- When executing from an attached implementation plan, follow the plan as written, do not edit the plan file, and work existing todo items to completion (mark in progress, then done) rather than recreating them. Delete the plan file when all items are done if the user requests it.
- Git commits and pushes must **never mention Cursor** (no "Made with Cursor", no Cursor references in commit messages or PR descriptions).
- GitHub account is **Sekoya88**; remote is `git@github.com:Sekoya88/Flow.git`, default branch `main`.
- For local Docker after code or migration changes, prefer **`make update`** from the repo root (rebuild api/worker/web, migrate, re-seed) instead of volume-wiping rebuilds unless a clean DB is intentional.

## Learned Workspace Facts

- **Flow** is a monorepo: `apps/web` uses Next.js 16, Tailwind v4, shadcn-style UI on Base UI primitives (JetBrains Mono, grain/gradient in root layout); `services/api` uses FastAPI, asyncpg, a LangGraph **deer-flow** pipeline (planner → worker → synthesizer), JWT, SSE for executions, workspaces, knowledge RAG, agent memory, and proposals.
- **Local Docker (typical host ports):** web on **13000** (maps to 3000), API/OpenAPI on **18000** (maps to 8000), Postgres on host **55432** (maps to 5432); `docker compose` and paths like `cd apps/web` / `cd services/api` are only valid from the **repo root**.
- **UX direction:** the user compares authenticated UI to **`lucis-agent/frontend`** (Vite reference): minimal shell, landing-style hierarchy and motion, static footer polish, and optional run/session context in the header vs a crowded horizontal nav.
- **Agent surface:** `agents.config.tools` (e.g. retrieve, sandbox, long_term_memory) is configurable via the existing **PATCH** agent flow; extension toward extra tools (HTTP, MCP, search) is a planned backend/contract concern.
- The Run flow streams over **SSE** (`EventSource`); the browser cannot send custom auth headers, so the app may pass tokens via query string today—treat URL logging and long-lived tokens as known hardening areas.
- **User profile / preferences:** `user_preferences` facets (`style`, `tooling`, `goal`, `veto`, `domain`, `channel`), onboarding at `/onboarding/profile`, CV import via Deep Agents (`FLOW_OPENAI_API_KEY` / `FLOW_ANTHROPIC_API_KEY` on instantiated chat models). Web **`apiFetch` must use `json:`** for preference POST/PATCH (not raw `JSON.stringify` without Content-Type). Onboarding POST uses **`workspace_id` as query param**.
- **Agentic RAG (optional):** Qdrant on host **16333**, enabled with `FLOW_AGENTIC_RAG_ENABLED` + `FLOW_QDRANT_URL`; knowledge ingest can dual-write Postgres + Qdrant.
- **Research digest:** LangGraph pipeline + UI `/research` (`/api/v1/digest/*`), Obsidian export paths under workspace digest config.
- **Cursor Obsidian MCP:** Project server `obsidian-vault` (vendor `obsidian-vault-mcp/`, `.cursor/mcp.json`) is separate from Flow **`services/mcp`** digest tools; both can share **`FLOW_OBSIDIAN_VAULT_PATH`** (quote paths with spaces in `.env`). See `docs/OBSIDIAN_VAULT_MCP.md`.


<claude-mem-context>
# Memory Context

# [Flow] recent context, 2026-04-27 12:03pm GMT+2

No previous sessions found.
</claude-mem-context>