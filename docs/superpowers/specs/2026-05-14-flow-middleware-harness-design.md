# Flow — Middleware Harness

**Date:** 2026-05-14
**Status:** Implemented (Phase 1 complete)
**Branch:** feat/agent-genome-versionning

---

## Problem

Flow agents lack a composable layer between the caller and the compiled LangGraph for cross-cutting concerns. As a result:

- **Resilience** is absent: transient LLM/tool failures (429, 503, timeout) crash executions outright
- **Memory injection** is post-hoc: `memory_judge.py` extracts facts after the run in a fire-and-forget task, making them available N+2 runs later instead of the very next run
- **Cost** is uncontrolled: long-running agents accumulate tokens indefinitely; no hard cap on LLM calls
- **Observability** via `FlowCallbackHandler` lacks state access: callbacks receive only what LangChain exposes, not the full graph state per node

LangChain's upcoming `create_agent(..., middleware=[...])` API (noted in docs, unconfirmed released in `langchain==1.3.0`) is not yet stable and only targets react-agent. Building on it now would block shipping.

---

## Scope

Build a `FlowMiddlewareHarness` that wraps any compiled LangGraph and implements four middleware classes:

1. `FlowMemoryMiddleware` — synchronous before/after hooks for cross-run memory
2. `FlowResilienceMiddleware` — retry + model fallback
3. `FlowCostMiddleware` — token-based summarization + call limit
4. `FlowObservabilityMiddleware` — state-aware wrap hooks replacing `FlowCallbackHandler`

**Phase 1** (this spec): wrap `react-agent` template only.
**Phase 2** (separate PR): extend harness to all graph templates (`linear-3`, `researcher-critic-writer`, etc.).

The harness implements the same `astream` / `aget_state` interface as a compiled LangGraph so `execution_runner.py` needs no changes.

---

## Architecture

### FlowMiddlewareHarness

```python
class FlowMiddlewareHarness:
    """Wraps a compiled LangGraph, running middleware before/after execution."""

    def __init__(self, graph: Any, middleware: list[AgentMiddleware]) -> None: ...

    # Same interface as compiled graph — execution_runner.py calls these unchanged
    async def astream(self, input, config, *, stream_mode=None, **kwargs): ...
    async def aget_state(self, config): ...
```

### AgentMiddleware base class

```python
class AgentMiddleware:
    """Override any subset of hooks. All are no-ops by default."""

    # Agent-level (fire once per run)
    async def before_agent(self, state: dict, runtime: HarnessRuntime) -> dict:
        return state

    async def after_agent(self, state: dict, runtime: HarnessRuntime) -> None:
        pass

    # Model-level (fire on every LLM call inside the graph)
    async def before_model(self, state: dict, runtime: HarnessRuntime) -> dict | None:
        return None  # None = no state mutation; {"jump_to": "end"} = early exit

    # Call-level (wrap each model/tool invocation)
    async def wrap_model_call(self, invoke: Callable, state: dict) -> Any:
        return await invoke(state)

    async def wrap_tool_call(self, invoke: Callable, state: dict) -> Any:
        return await invoke(state)
```

### HarnessRuntime

```python
@dataclass
class HarnessRuntime:
    workspace_id: UUID
    agent_id: UUID
    user_id: UUID
    execution_id: UUID
    thread_id: str
```

Passed to all hooks. Carries the execution context without needing global state.

### Execution order

```
before_agent hooks (index 0 → N)
  │
  ▼
graph.astream()  ← LLM is a _WrappedLLM proxy; wrap_model_call + before_model fire per call
  │               ← tools are _WrappedTool proxies; wrap_tool_call fires per call
  ▼
after_agent hooks (index 0 → N)
```

**How `wrap_model_call` / `wrap_tool_call` work inside a compiled graph:**

`FlowMiddlewareHarness` accepts the `llm` and `tools` objects directly (not a pre-compiled graph). It wraps them in thin proxy classes (`_WrappedLLM`, `_WrappedTool`) that call the middleware chain on every `ainvoke`/`astream` call, then compiles the graph internally. External callers see only the harness — not the underlying graph.

```python
# harness builds the graph, not wraps a pre-built one
harness = FlowMiddlewareHarness(
    llm=llm, tools=tools, middleware=[...],
    checkpointer=checkpointer, store=store,
    template=template,  # "react-agent" | "deer-flow"
)
```

`before_agent` fires once before `graph.astream()`. `after_agent` fires once after all chunks are consumed and final state is read. `before_model` fires before every LLM call (via `_WrappedLLM`). `wrap_model_call` / `wrap_tool_call` surround every call.

---

## Middleware

### 1. FlowMemoryMiddleware (Priority: highest)

**Purpose:** Replace `memory_judge.py` fire-and-forget with synchronous hook-based memory.

```python
FlowMemoryMiddleware(
    store: AsyncPostgresStore,
    llm: BaseChatModel | None,          # gpt-4o-mini for extraction
    embed: Callable[[str], Awaitable],  # wraps emb_svc.embed_texts
    max_facts: int = 8,
    min_confidence: float = 0.7,        # threshold for pattern storage
)
```

**`before_agent`** — inject relevant memory into initial state:

1. Query `store.asearch((ws_id, agent_id, "facts"), query=last_user_message, limit=max_facts)`
2. Query `store.asearch((ws_id, agent_id, "patterns"), query=last_user_message, limit=3)`
3. If results found: prepend a `SystemMessage(content=formatted_memory_block)` to `state["messages"]`
4. Return augmented state (or original state if store is empty — no-op)

**`after_agent`** — extract and store facts synchronously:

1. Extract answer from `state.get("answer")` or last AI message content
2. Call `extract_facts_from_answer(llm, question, answer)` (reuse from `memory_judge.py`)
3. For each fact: compute embedding, call `store.aput((ws_id, agent_id, "facts"), stable_key(fact), ...)`
4. If `state.get("confidence", 0) >= min_confidence`: call `extract_pattern_summary`, store under `"patterns"` namespace

**Migration from `execution_runner.py`:**

Delete lines 238–282 (the LLM-judge memory extraction block) after `FlowMemoryMiddleware` is wired in. The `extract_facts_from_answer`, `extract_pattern_summary`, and `should_store_pattern` functions in `memory_judge.py` are reused — do not delete them.

---

### 2. FlowResilienceMiddleware

**Purpose:** Retry transient errors; fall back to a cheaper model on exhaustion.

```python
FlowResilienceMiddleware(
    model_retry: int = 3,
    tool_retry: int = 2,
    backoff_factor: float = 1.5,       # retry delays: 1s, 1.5s, 2.25s
    fallback_model: str | None = "gpt-4o-mini",
    fallback_api_key: str | None = None,
)
```

**`wrap_model_call`:**

1. Retry up to `model_retry` times on `RateLimitError`, `APIStatusError` (5xx), `APITimeoutError` using `tenacity.retry` with exponential backoff
2. On final exhaustion: if `fallback_model` set, swap the model in the call args and attempt once
3. On fallback exhaustion: re-raise original exception (captured and logged by `execution_runner.py`)

**`wrap_tool_call`:**

1. Retry up to `tool_retry` times on any exception
2. On final failure: log `tool.failed` with error + tool name, continue execution (do not crash run)

**New dependency:** `tenacity>=8.0` — lightweight retry library, no transitive deps.

---

### 3. FlowCostMiddleware

**Purpose:** Prevent token runaway and unbounded LLM call loops.

```python
FlowCostMiddleware(
    token_limit: int = 80_000,
    call_limit: int = 30,
    summarize_model: BaseChatModel,
    token_counter: Callable[[list[BaseMessage]], int],  # tiktoken wrapper
)
```

**`before_model` hook** (fires before each model call inside the graph):

1. Increment `state["model_call_count"]` (custom state extension via `FlowCostState`)
2. If `model_call_count >= call_limit`: return `{"jump_to": "end"}` — exits agent cleanly
3. Count tokens in `state["messages"]`
4. If tokens > `token_limit`: summarize oldest messages (keep last 4 intact), replace with a single `AIMessage(content=summary)`, update `state["tokens_summarized"]`

**Custom state extension:**

```python
class FlowCostState(TypedDict, total=False):
    model_call_count: int
    tokens_summarized: int
```

**New dependency:** `tiktoken>=0.7` — OpenAI's tokenizer, works as a general-purpose BPE counter.

---

### 4. FlowObservabilityMiddleware

**Purpose:** Replace `FlowCallbackHandler` with state-aware wrap hooks that have access to full graph state.

```python
FlowObservabilityMiddleware(
    logger: BoundLogger,  # structlog logger with execution_id pre-bound
)
```

**`wrap_model_call`:**

```
t0 = time.monotonic()
response = await invoke(state)
log model.end: latency_ms, input_tokens, output_tokens, model_id, node_name
return response
```

**`wrap_tool_call`:**

```
t0 = time.monotonic()
try:
    result = await invoke(state)
    log tool.end: tool_name, duration_ms, status=ok
    return result
except Exception as e:
    log tool.error: tool_name, error, duration_ms
    raise
```

**Advantage over `FlowCallbackHandler`:**
- Full `state` dict access (current node, plan, messages, confidence)
- Async-native — no sync-to-async adapter
- Fires on actual execution, not LangChain callback events

**Migration:** Once `FlowObservabilityMiddleware` is wired into the harness, remove `"callbacks": [_callback]` from `execution_runner.py` run config and delete `FlowCallbackHandler` instantiation there. Keep `infrastructure/observability/callbacks.py` for Phase 2 multi-node graphs.

---

## agent_factory.py integration

```python
def build_agent_from_ctx(ctx: GraphContext, checkpointer=None) -> FlowMiddlewareHarness:
    spec = spec_from_config(ctx.agent_config)
    model_cfg = ctx.agent_config.get("model") or {}
    llm = get_chat_model(model_cfg, {"openai": ctx.openai_api_key, "anthropic": ctx.anthropic_api_key})
    tools = _get_tools_for_ctx(ctx)   # existing tool resolution logic

    middleware: list[AgentMiddleware] = []

    if ctx.store is not None:
        _judge_llm = _get_llm_for_judge_ctx(ctx)
        middleware.append(FlowMemoryMiddleware(
            store=ctx.store, llm=_judge_llm,
            embed=lambda t: emb_svc.embed_texts(ctx.settings.openai_api_key, [t]),
        ))

    middleware.append(FlowResilienceMiddleware(
        fallback_model="gpt-4o-mini",
        fallback_api_key=ctx.openai_api_key,
    ))

    if _judge_llm := _get_llm_for_judge_ctx(ctx):
        middleware.append(FlowCostMiddleware(
            summarize_model=_judge_llm,
            token_counter=tiktoken_token_counter,
        ))

    middleware.append(FlowObservabilityMiddleware(
        logger=get_logger("flow.agent").bind(
            execution_id=str(ctx.execution_id),
            agent_id=str(ctx.agent_id),
            workspace_id=str(ctx.workspace_id),
        )
    ))

    return FlowMiddlewareHarness(
        llm=llm, tools=tools, middleware=middleware,
        checkpointer=checkpointer, store=ctx.store,
        template=spec.template,
    )
```

`_build_raw_graph` is the current `build_agent_from_ctx` routing logic extracted to a private function. The public function now always returns a `FlowMiddlewareHarness`.

---

## Files changed

| File | Action | Notes |
|------|--------|-------|
| `infrastructure/llm/middleware/__init__.py` | New | Re-exports all middleware classes |
| `infrastructure/llm/middleware/base.py` | New | `AgentMiddleware`, `FlowMiddlewareHarness`, `HarnessRuntime` |
| `infrastructure/llm/middleware/memory.py` | New | `FlowMemoryMiddleware` |
| `infrastructure/llm/middleware/resilience.py` | New | `FlowResilienceMiddleware` |
| `infrastructure/llm/middleware/cost.py` | New | `FlowCostMiddleware` |
| `infrastructure/llm/middleware/observability.py` | New | `FlowObservabilityMiddleware` |
| `infrastructure/llm/agent_factory.py` | Modify | Wrap graph with `FlowMiddlewareHarness` |
| `application/execution_runner.py` | Modify | Remove lines 238–282 (memory judge block), remove `callbacks` from run config |
| `pyproject.toml` | Modify | Add `tenacity>=8.0`, `tiktoken>=0.7` |

---

## Dependencies added

| Package | Version | Reason |
|---------|---------|--------|
| `tenacity` | `>=8.0,<10` | Retry with backoff for model/tool calls |
| `tiktoken` | `>=0.7,<1` | Token counting for conversation summarization threshold |

---

## Phase 2 scope (out of scope for this spec)

Separate PR after Phase 1 is stable:

- Extend `FlowMiddlewareHarness` wrapping to `build_deer_flow_graph` output in `agent_factory.py`
- Remove manual `store.asearch` / `store.aput` from `nodes.py` (planner ~line 255, synthesizer ~line 417) — `FlowMemoryMiddleware.before_agent` handles it uniformly
- Remove `FlowCallbackHandler` instantiation from `execution_runner.py` entirely — `FlowObservabilityMiddleware` covers it

---

## Testing

Each middleware tested in isolation. The graph is replaced by a stub that records call order and arguments.

| File | What it verifies |
|------|-----------------|
| `tests/test_middleware_memory.py` | `before_agent` injects facts; `after_agent` stores facts; no-op if store empty; min_confidence gate works |
| `tests/test_middleware_resilience.py` | Retries on 429/503; switches model after exhaustion; continues on tool error without crashing |
| `tests/test_middleware_cost.py` | Summarizes at token threshold; stops at call_limit via `jump_to=end`; state counters increment |
| `tests/test_middleware_observability.py` | Logs `latency_ms`, `input_tokens`, `output_tokens` per call; `tool.error` logged and re-raised |
| `tests/test_middleware_harness.py` | Stack execution order (before: 0→N, after: 0→N); hook exception doesn't crash run; `astream` passthrough |

---

## Success criteria

1. `react-agent` executions survive transient 429 / 503 errors without surfacing to the user
2. Facts extracted from run N are available in run N+1 (injected via `before_agent`)
3. Agents with > 80k token conversations summarize automatically; no run exceeds 30 model calls
4. `docker logs flow-api-1` shows `model.end` with `latency_ms` and token counts on every LLM call
5. Deleting lines 238–282 from `execution_runner.py` causes no test regressions
6. All 5 test files pass; existing test suite shows no regressions
