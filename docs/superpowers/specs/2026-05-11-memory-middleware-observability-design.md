# Flow — Memory, Middleware & Observability

**Date:** 2026-05-11  
**Status:** Approved  
**Branch:** feat/agent-genome-versionning

---

## Problem

Flow has per-run in-thread memory (LangGraph `AsyncPostgresSaver`) and a Qdrant-backed
long-term memory tool, but lacks:

- Cross-thread persistent memory store (`AsyncPostgresStore`) — facts learned in run #1
  are unavailable in run #2 unless the agent re-discovers them
- LangChain-native middleware (prompt caching, state memory tool for Anthropic models)
- Structured correlation in logs — `execution_id / agent_id / workspace_id` not always
  present in every log line
- Docker containers logging in plain text (`FLOW_LOG_JSON: "false"`) — no machine-parseable
  output in prod-like deployments

---

## Scope

This spec covers four phases. It does **not** rewrite the multi-node graph templates
(`linear-3`, `researcher-critic-writer`, etc.); those topologies are core to Flow's value
and are preserved. The `create_agent` path is **additive**: a new `"react-agent"` template
type for simple ReAct-style Anthropic agents.

---

## Architecture

### Memory layers (after)

```text
┌─────────────────────────────────────────────────────┐
│                 Agent Execution                      │
│                                                     │
│  ┌──────────────┐    ┌──────────────────────────┐   │
│  │  In-thread   │    │    Cross-thread store    │   │
│  │  checkpointer│    │   AsyncPostgresStore     │   │
│  │  (per thread)│    │  namespace: (ws, agent,  │   │
│  │  messages,   │    │   "facts" | "patterns")  │   │
│  │  plan, state │    │  semantic search + put   │   │
│  └──────────────┘    └──────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### Agent factory routing

```text
agent_config.template
    ├── "react-agent" + provider="anthropic"
    │       → create_agent(ChatAnthropic,
    │             middleware=[StateClaudeMemoryMiddleware(),
    │                         AnthropicPromptCachingMiddleware()])
    │         + store + checkpointer attached
    │
    └── all other templates (linear-3, researcher-critic-writer, etc.)
            → build_deer_flow_graph(ctx, checkpointer, store)
              + FlowCallbackHandler attached to model calls
```

### Observability stack (after)

```text
Execution start
  │
  ├─ structlog.bind_contextvars(execution_id, agent_id, workspace_id, template)
  ├─ LangSmith run_extra metadata (same IDs)
  │
  ▼
FlowCallbackHandler (BaseCallbackHandler)
  ├── on_llm_start    → log model, provider, node_name
  ├── on_llm_end      → log latency_ms, input_tokens, output_tokens
  ├── on_tool_start   → log tool_name, input_preview
  ├── on_tool_end     → log duration_ms, status
  └── on_chain_error  → log error, traceback
  │
  ▼
structlog (JSON in Docker, colored in dev TTY)
  +
LangSmith trace (enriched with workspace/agent/execution metadata)
```

---

## Phase 1 — AsyncPostgresStore (cross-thread memory)

### New file: `infrastructure/db/store.py`

Builds and manages an `AsyncPostgresStore` instance backed by the same Postgres DB.
Exposes `build_memory_store(database_url)` returning an `AsyncPostgresStore`.

### Changes to `infrastructure/graph/spec.py`

`compile_graph` gains a `store: Any | None = None` parameter passed to `g.compile()`.

### Changes to `infrastructure/graph/deer_graph.py`

`GraphContext` gains `store: Any | None = None` field.
`build_deer_flow_graph` passes `store=ctx.store` to `compile_graph`.

### Changes to `interfaces/http/main.py`

Lifespan creates `memory_store = AsyncPostgresStore(...)`, calls `await memory_store.setup()`,
attaches to `app.state.memory_store`.

### Changes to `infrastructure/queue/worker.py`

Startup creates and opens the memory store alongside checkpoint pool.
Passes `store` through the execution context.

### Changes to `application/execution_runner.py`

Receives `store` parameter, passes it to `GraphContext`.

### Changes to `infrastructure/graph/nodes.py`

- Memory retrieval: before planner runs, call `store.asearch(namespace, query, limit=5)`
  and inject results into system prompt context.
- Memory write: after synthesizer/writer runs, call `store.aput` to persist extracted facts
  (replaces current `memory_judge.py` asyncio fire-and-forget).

### Namespaces

| Namespace | Content | Written by |
|-----------|---------|------------|
| `(ws_id, agent_id, "facts")` | Short atomic facts from `memory_judge` | synthesizer/writer node |
| `(ws_id, agent_id, "patterns")` | Problem/solution summaries | execution_runner post-run |
| `(ws_id, user_id, "preferences")` | User preferences (future) | reserved |

---

## Phase 2 — Agent factory + Anthropic middleware

### New file: `infrastructure/llm/agent_factory.py`

```python
def build_agent(ctx: GraphContext, checkpointer, store) -> CompiledGraph:
    template = spec_from_config(ctx.agent_config).template
    provider = ctx.agent_config.get("model", {}).get("provider", "openai")

    if template == "react-agent" and provider == "anthropic":
        return _build_anthropic_react_agent(ctx, checkpointer, store)
    return build_deer_flow_graph(ctx, checkpointer)  # store passed via ctx
```

`_build_anthropic_react_agent` uses `langchain.agents.create_agent` with:

- `StateClaudeMemoryMiddleware(allowed_path_prefixes=["/memories"])`
- `AnthropicPromptCachingMiddleware(ttl="5m")`
- `checkpointer` and `store` wired in

### New template in `spec.py`

Add `"react-agent"` to `TEMPLATES` as a marker spec (single-node, routes to `agent_factory`).

### Changes to `execution_runner.py` and `worker.py`

Replace `build_deer_flow_graph` calls with `agent_factory.build_agent(...)`.

---

## Phase 3 — Logging & LangSmith enrichment

### New file: `infrastructure/observability/callbacks.py`

`FlowCallbackHandler(BaseCallbackHandler)`:

- `on_llm_start` — log `model.start` with model name, node, tokens-in estimate
- `on_llm_end` — log `model.end` with latency_ms, prompt_tokens, completion_tokens
- `on_tool_start` — log `tool.start` with tool name, input preview
- `on_tool_end` — log `tool.end` with duration_ms
- `on_chain_error` — log `chain.error` with exception type, message

All events use `structlog` — already has `execution_id/agent_id` bound via contextvars.

### LangSmith run metadata

In `execution_runner.py`, pass `run_extra={"metadata": {"workspace_id": ..., "agent_id": ...,
"execution_id": ..., "template": ...}}` via `RunnableConfig` tags so LangSmith traces are filterable.

### Docker logging

`docker-compose.yml`:

- `api`: `FLOW_LOG_JSON: "true"` — JSON structured output for log aggregators
- `worker`: `FLOW_LOG_JSON: "true"`

Dev override stays: `FLOW_LOG_JSON: "false"` in `.env.example` for colored local dev.

### `logging.py` improvement

`service`, `execution_id`, `agent_id` already propagate to JSON via the `merge_contextvars`
processor — no structural change needed.

---

## Phase 4 — Architecture diagram

Update `flow-architecture.drawio` to show:

- Memory layer: checkpointer (in-thread) + store (cross-thread)
- Middleware stack: `StateClaudeMemoryMiddleware`, `AnthropicPromptCachingMiddleware`
- Callback handler: `FlowCallbackHandler` → structlog → LangSmith
- Agent factory routing: react-agent vs template graphs

---

## Files changed

| File | Action |
|------|--------|
| `infrastructure/db/store.py` | New |
| `infrastructure/llm/agent_factory.py` | New |
| `infrastructure/observability/callbacks.py` | New |
| `infrastructure/graph/spec.py` | Add `store` param, add `react-agent` template |
| `infrastructure/graph/deer_graph.py` | Add `store` to `GraphContext`, pass to compile |
| `infrastructure/graph/nodes.py` | Memory retrieval + store.aput in synthesis |
| `application/execution_runner.py` | Accept/pass `store`, use `agent_factory`, LangSmith metadata |
| `infrastructure/queue/worker.py` | Build/open/close memory store |
| `interfaces/http/main.py` | Build/setup/close memory store in lifespan |
| `docker-compose.yml` | `FLOW_LOG_JSON: "true"` for api + worker |
| `flow-architecture.drawio` | Update with new components |

---

## Dependencies added

| Package              | Version | Reason                                                                    |
|----------------------|---------|---------------------------------------------------------------------------|
| `langchain>=1.2,<2`  | New     | `langchain.agents.create_agent` + middleware                              |
| (no new package)     | —       | `AsyncPostgresStore` in `langgraph-checkpoint-postgres` (already in deps) |

**Correct import paths:**

- `from langgraph.store.postgres.aio import AsyncPostgresStore`
- `from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver` (unchanged)
- `from langchain.agents import create_agent`
- `from langchain_anthropic.middleware import StateClaudeMemoryMiddleware, AnthropicPromptCachingMiddleware`

**Store access in nodes** uses `InjectedStore` pattern:

```python
from langgraph.store.base import BaseStore, InjectedStore
from typing import Annotated

async def planner_node(state: FlowGraphState, store: Annotated[BaseStore, InjectedStore()]):
    facts = await store.asearch(namespace, query=state["messages"][-1].content)
```

---

## Constraints & non-goals

- No change to existing graph templates (linear-3, researcher-critic-writer, etc.)
- No change to DB schema — `AsyncPostgresStore` manages its own tables via `.setup()`
- `react-agent` template is additive; no existing agents are migrated automatically
- `deepagents` package is NOT added — Flow uses `langchain.agents.create_agent` directly
- All changes backward-compatible with existing agents

---

## Success criteria

1. Existing agents run unchanged — no regression in graph execution
2. New `react-agent` template works end-to-end in browser with Anthropic model
3. `StateClaudeMemoryMiddleware`: agent reads/writes `/memories` in state between turns
4. `AnthropicPromptCachingMiddleware`: LangSmith shows cache hits on repeated runs
5. Docker `docker logs flow-api-1` outputs valid JSON lines with `execution_id` field
6. LangSmith traces filterable by `workspace_id`, `agent_id`, `execution_id`
7. `AsyncPostgresStore` facts persist across executions (verify via memory routes)
