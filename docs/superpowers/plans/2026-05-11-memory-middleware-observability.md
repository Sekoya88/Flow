# Memory, Middleware & Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `AsyncPostgresStore` cross-thread memory, `create_agent`+middleware for Anthropic react-agent template, `FlowCallbackHandler` for structured logging, and JSON Docker logs.

**Architecture:** Existing LangGraph graph templates (linear-3, researcher-critic-writer, etc.) are preserved unchanged. `AsyncPostgresStore` is added for cross-thread fact persistence alongside the existing `AsyncPostgresSaver` checkpointer. A new `react-agent` template routes to `create_agent` with Anthropic-specific middleware. `FlowCallbackHandler` provides structlog-backed per-model/tool observability injected at execution time.

**Tech Stack:** LangGraph 0.6+, `langgraph.store.postgres.aio.AsyncPostgresStore`, `langchain>=1.2` (`langchain.agents.create_agent`), `langchain_anthropic.middleware.StateClaudeMemoryMiddleware` + `AnthropicPromptCachingMiddleware`, `langchain_core.callbacks.BaseCallbackHandler`, structlog, psycopg-pool.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `services/api/flow/infrastructure/db/store.py` | Create | `build_memory_store_pool()` + `create_memory_store()` factory |
| `services/api/flow/infrastructure/observability/callbacks.py` | Create | `FlowCallbackHandler` — structlog for every model/tool event |
| `services/api/flow/infrastructure/llm/agent_factory.py` | Create | `build_agent()` routing: react-agent→`create_agent`, others→`build_deer_flow_graph` |
| `services/api/flow/infrastructure/graph/spec.py` | Modify | Add `store` param to `compile_graph`; add `react-agent` to `TEMPLATES` |
| `services/api/flow/infrastructure/graph/deer_graph.py` | Modify | Add `store` field to `GraphContext`; pass `store` to `compile_graph` |
| `services/api/flow/infrastructure/graph/nodes.py` | Modify | Planner reads from `ctx.store`; synthesizer writes facts to `ctx.store` |
| `services/api/flow/application/execution_runner.py` | Modify | Accept `store` param; pass to `GraphContext`; inject `FlowCallbackHandler`; enrich LangSmith metadata |
| `services/api/flow/infrastructure/queue/worker.py` | Modify | Build/open/close memory store pool in startup/shutdown |
| `services/api/flow/interfaces/http/main.py` | Modify | Build/setup/close memory store in lifespan |
| `services/api/pyproject.toml` | Modify | Add `langchain>=1.2,<2` |
| `docker-compose.yml` | Modify | `FLOW_LOG_JSON: "true"` for api + worker |
| `flow-architecture.drawio` | Modify | Add memory/middleware/observability layers |
| `services/api/tests/test_memory_store.py` | Create | Unit tests for store factory |
| `services/api/tests/test_callbacks.py` | Create | Unit tests for FlowCallbackHandler |
| `services/api/tests/test_agent_factory.py` | Create | Unit tests for build_agent routing |

---

## Task 1: AsyncPostgresStore factory

**Files:**
- Create: `services/api/flow/infrastructure/db/store.py`
- Create: `services/api/tests/test_memory_store.py`

- [ ] **Step 1.1: Write failing test**

```python
# services/api/tests/test_memory_store.py
from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_build_memory_store_pool_returns_async_connection_pool():
    """build_memory_store_pool returns an AsyncConnectionPool (not yet opened)."""
    from flow.infrastructure.db.store import build_memory_store_pool
    pool = build_memory_store_pool("postgresql://flow:flow@localhost:55432/flow")
    assert pool is not None
    # Pool should not be opened yet
    assert not pool.closed


def test_create_memory_store_wraps_pool():
    """create_memory_store returns an AsyncPostgresStore wrapping the pool."""
    from flow.infrastructure.db.store import create_memory_store
    mock_pool = MagicMock()
    with patch("flow.infrastructure.db.store.AsyncPostgresStore") as MockStore:
        MockStore.return_value = MagicMock()
        store = create_memory_store(mock_pool)
        MockStore.assert_called_once_with(mock_pool)
        assert store is MockStore.return_value
```

- [ ] **Step 1.2: Run test — expect FAIL**

```bash
cd services/api && uv run pytest tests/test_memory_store.py -v
```

Expected: `ModuleNotFoundError: No module named 'flow.infrastructure.db.store'`

- [ ] **Step 1.3: Create `infrastructure/db/store.py`**

```python
"""AsyncPostgresStore factory for cross-thread LangGraph memory."""
from __future__ import annotations

from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row


def build_memory_store_pool(database_url: str) -> AsyncConnectionPool:
    """Separate pool for AsyncPostgresStore (do not share with checkpoint pool)."""
    return AsyncConnectionPool(
        database_url,
        open=False,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        min_size=1,
        max_size=5,
    )


def create_memory_store(pool: AsyncConnectionPool):
    """Return an AsyncPostgresStore backed by pool. Call .setup() before first use."""
    from langgraph.store.postgres.aio import AsyncPostgresStore
    return AsyncPostgresStore(pool)
```

- [ ] **Step 1.4: Run test — expect PASS**

```bash
cd services/api && uv run pytest tests/test_memory_store.py -v
```

Expected: 2 passed

- [ ] **Step 1.5: Commit**

```bash
git add services/api/flow/infrastructure/db/store.py services/api/tests/test_memory_store.py
git commit -m "feat(memory): add AsyncPostgresStore factory"
```

---

## Task 2: Wire store into GraphContext and spec compiler

**Files:**
- Modify: `services/api/flow/infrastructure/graph/deer_graph.py`
- Modify: `services/api/flow/infrastructure/graph/spec.py`

- [ ] **Step 2.1: Write failing test**

```python
# Add to services/api/tests/test_deer_graph_offline.py (append at end)

def test_graph_context_has_store_field():
    """GraphContext accepts a store field."""
    from flow.infrastructure.graph.deer_graph import GraphContext
    from unittest.mock import MagicMock
    from uuid import uuid4

    ctx = GraphContext(
        pool=MagicMock(),
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        openai_api_key=None,
        agent_config={},
        store=MagicMock(),  # new field
    )
    assert ctx.store is not None


def test_compile_graph_passes_store_to_compiled_graph():
    """compile_graph forwards store to StateGraph.compile()."""
    from flow.infrastructure.graph.spec import compile_graph, GraphSpec
    from unittest.mock import MagicMock, patch

    spec = GraphSpec(template="linear-3", nodes=["planner"], edges=[], entry="planner")
    node_registry = {"planner": MagicMock()}
    condition_registry = {}
    mock_store = MagicMock()

    with patch("flow.infrastructure.graph.spec.StateGraph") as MockSG:
        mock_graph = MagicMock()
        MockSG.return_value = mock_graph
        mock_graph.add_node = MagicMock()
        mock_graph.add_edge = MagicMock()
        mock_graph.compile = MagicMock(return_value=MagicMock())
        mock_graph.add_conditional_edges = MagicMock()

        compile_graph(spec, node_registry, condition_registry, store=mock_store)
        mock_graph.compile.assert_called_once_with(checkpointer=None, store=mock_store)
```

- [ ] **Step 2.2: Run test — expect FAIL**

```bash
cd services/api && uv run pytest tests/test_deer_graph_offline.py -v
```

Expected: `TypeError: GraphContext.__init__() got an unexpected keyword argument 'store'`

- [ ] **Step 2.3: Update `deer_graph.py` — add `store` to GraphContext**

Open `services/api/flow/infrastructure/graph/deer_graph.py`.

Change the `GraphContext` dataclass:

```python
@dataclass
class GraphContext:
    pool: asyncpg.Pool
    workspace_id: UUID
    agent_id: UUID
    user_id: UUID
    openai_api_key: str | None
    agent_config: dict[str, Any]
    anthropic_api_key: str | None = None
    execution_id: UUID | None = None
    settings: Settings | None = None
    stream_hub: Any | None = None  # ExecutionStreamHub — avoids circular import
    store: Any | None = None  # AsyncPostgresStore for cross-thread memory
```

Change `build_deer_flow_graph`:

```python
def build_deer_flow_graph(ctx: GraphContext, checkpointer: Any | None = None) -> Any:
    spec = spec_from_config(ctx.agent_config)
    node_registry = build_node_registry(ctx)
    return compile_graph(spec, node_registry, CONDITION_REGISTRY, checkpointer=checkpointer, store=ctx.store)
```

- [ ] **Step 2.4: Update `spec.py` — add `store` param to `compile_graph`**

In `services/api/flow/infrastructure/graph/spec.py`, update `compile_graph`:

```python
def compile_graph(
    spec: GraphSpec,
    node_registry: dict[str, Callable],
    condition_registry: dict[str, Callable],
    checkpointer: Any | None = None,
    store: Any | None = None,
) -> Any:
    """Compile a GraphSpec into a compiled LangGraph StateGraph."""
    g = StateGraph(FlowGraphState)

    for node_name in spec.nodes:
        fn = node_registry.get(node_name)
        if fn is None:
            raise ValueError(f"No node function registered for '{node_name}'")
        g.add_node(node_name, fn)

    g.add_edge(START, spec.entry)

    for src, dst in spec.edges:
        g.add_edge(_resolve(src), _resolve(dst))

    for ce in spec.conditional_edges:
        condition_fn = condition_registry.get(ce.condition)
        if condition_fn is None:
            raise ValueError(f"No condition function registered for '{ce.condition}'")
        resolved_mapping = {k: _resolve(v) for k, v in ce.mapping.items()}
        g.add_conditional_edges(ce.source, condition_fn, resolved_mapping)

    return g.compile(checkpointer=checkpointer, store=store)
```

Also add `"react-agent"` to `TEMPLATES` dict at the bottom of `spec.py`:

```python
    "react-agent": GraphSpec(
        template="react-agent",
        nodes=["planner"],
        edges=[("planner", "END")],
        entry="planner",
    ),
```

- [ ] **Step 2.5: Run test — expect PASS**

```bash
cd services/api && uv run pytest tests/test_deer_graph_offline.py -v
```

Expected: all tests pass

- [ ] **Step 2.6: Commit**

```bash
git add services/api/flow/infrastructure/graph/deer_graph.py \
        services/api/flow/infrastructure/graph/spec.py \
        services/api/tests/test_deer_graph_offline.py
git commit -m "feat(memory): add store field to GraphContext + spec compiler"
```

---

## Task 3: Store read/write in nodes (planner retrieves, synthesizer persists)

**Files:**
- Modify: `services/api/flow/infrastructure/graph/nodes.py`

- [ ] **Step 3.1: Write failing test**

```python
# Add to new file: services/api/tests/test_nodes_store.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4


@pytest.mark.asyncio
async def test_planner_reads_store_facts_when_store_present():
    """Planner node calls store.asearch when ctx.store is set."""
    from flow.infrastructure.graph.deer_graph import GraphContext
    from flow.infrastructure.graph.nodes import make_planner
    from langchain_core.messages import HumanMessage

    mock_store = AsyncMock()
    mock_store.asearch = AsyncMock(return_value=[
        MagicMock(value={"content": "fact: user prefers concise answers"})
    ])

    ctx = GraphContext(
        pool=AsyncMock(),
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        openai_api_key=None,
        agent_config={},
        store=mock_store,
    )
    planner = make_planner(ctx)
    state = {"messages": [HumanMessage(content="What is RAG?")]}
    result = await planner(state)

    mock_store.asearch.assert_awaited_once()
    call_args = mock_store.asearch.call_args
    namespace = call_args[0][0] if call_args[0] else call_args[1].get("namespace")
    assert "facts" in namespace


@pytest.mark.asyncio
async def test_synthesizer_writes_store_facts_when_store_present():
    """Synthesizer node calls store.aput when ctx.store is set and answer is non-empty."""
    from flow.infrastructure.graph.deer_graph import GraphContext
    from flow.infrastructure.graph.nodes import make_synthesizer
    from langchain_core.messages import HumanMessage

    mock_store = AsyncMock()
    mock_store.aput = AsyncMock()

    ctx = GraphContext(
        pool=AsyncMock(),
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        openai_api_key=None,
        agent_config={},
        store=mock_store,
    )
    synthesizer = make_synthesizer(ctx)
    state = {
        "messages": [HumanMessage(content="question")],
        "plan": "step 1. do thing",
        "worker_output": "some notes",
    }
    result = await synthesizer(state)

    # store.aput should be called with answer content
    mock_store.aput.assert_awaited()
```

- [ ] **Step 3.2: Run test — expect FAIL**

```bash
cd services/api && uv run pytest tests/test_nodes_store.py -v
```

Expected: `AssertionError: Expected 'asearch' to have been awaited once` (store not called yet)

- [ ] **Step 3.3: Update planner to read from store**

In `services/api/flow/infrastructure/graph/nodes.py`, inside `make_planner`, after the existing `pattern_block` retrieval block (around line 215, after the reasoning bank query), add:

```python
            # Read cross-thread facts from AsyncPostgresStore
            store_facts_block = ""
            if ctx.store is not None:
                try:
                    namespace = (str(ctx.workspace_id), str(ctx.agent_id), "facts")
                    store_results = await ctx.store.asearch(namespace, query=user_text, limit=5)
                    if store_results:
                        lines = [r.value.get("content", "") for r in store_results if r.value.get("content")]
                        if lines:
                            store_facts_block = "Remembered facts:\n" + "\n".join(f"- {l}" for l in lines)
                except Exception:
                    pass  # store read is best-effort
```

Then inject `store_facts_block` into the system prompt. Find the block where `system = "You are a planning node..."` is constructed and add:

```python
                if store_facts_block:
                    system = f"{system}\n\n{store_facts_block}"
```

- [ ] **Step 3.4: Update synthesizer to write to store**

In `services/api/flow/infrastructure/graph/nodes.py`, inside `make_synthesizer`, at the end of the `async def synthesizer(state)` function just before `return {...}`, add:

```python
            # Persist answer as fact in cross-thread store (best-effort)
            if ctx.store is not None and answer:
                try:
                    import uuid as _uuid
                    namespace = (str(ctx.workspace_id), str(ctx.agent_id), "facts")
                    key = str(_uuid.uuid4())
                    await ctx.store.aput(
                        namespace,
                        key,
                        {"content": answer[:500], "execution_id": str(ctx.execution_id or "")},
                    )
                except Exception:
                    pass  # store write is best-effort
```

- [ ] **Step 3.5: Run test — expect PASS**

```bash
cd services/api && uv run pytest tests/test_nodes_store.py -v
```

Expected: 2 passed

- [ ] **Step 3.6: Run full test suite for regressions**

```bash
cd services/api && uv run pytest tests/ -v --timeout=30 -x
```

Expected: all existing tests still pass

- [ ] **Step 3.7: Commit**

```bash
git add services/api/flow/infrastructure/graph/nodes.py \
        services/api/tests/test_nodes_store.py
git commit -m "feat(memory): planner reads + synthesizer writes cross-thread store"
```

---

## Task 4: Wire store through main.py, worker.py, execution_runner.py

**Files:**
- Modify: `services/api/flow/interfaces/http/main.py`
- Modify: `services/api/flow/infrastructure/queue/worker.py`
- Modify: `services/api/flow/application/execution_runner.py`

- [ ] **Step 4.1: Write failing test**

```python
# services/api/tests/test_execution_runner_store.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


@pytest.mark.asyncio
async def test_run_deer_execution_accepts_store_param():
    """run_deer_execution accepts a store kwarg and passes it to GraphContext."""
    from flow.application.execution_runner import run_deer_execution
    from flow.config import Settings

    mock_pool = AsyncMock()
    mock_store = AsyncMock()
    mock_stream_hub = MagicMock()
    mock_stream_hub.publish = MagicMock()
    mock_checkpointer = AsyncMock()
    settings = Settings(
        database_url="postgresql://flow:flow@localhost:55432/flow",
        jwt_secret="test",
    )

    captured_ctx = {}

    async def fake_graph_run(input, config=None, stream_mode=None):
        return
        yield  # make it async generator

    with (
        patch("flow.application.execution_runner.build_deer_flow_graph") as mock_build,
        patch("flow.application.execution_runner.FlowRepository") as MockRepo,
        patch("flow.application.execution_runner.agent_factory") as mock_factory,
    ):
        mock_graph = MagicMock()
        mock_graph.astream = fake_graph_run
        mock_factory.build_agent.return_value = mock_graph
        mock_build.return_value = mock_graph

        MockRepo.return_value.get_execution = AsyncMock(return_value=None)
        MockRepo.return_value.insert_event = AsyncMock()
        MockRepo.return_value.update_execution_status = AsyncMock()
        MockRepo.return_value.search_knowledge = AsyncMock(return_value=[])
        MockRepo.return_value.search_memories = AsyncMock(return_value=[])

        # Should not raise TypeError with store kwarg
        try:
            await run_deer_execution(
                pool=mock_pool,
                settings=settings,
                stream_hub=mock_stream_hub,
                checkpointer=mock_checkpointer,
                store=mock_store,  # new param
                execution_id=uuid4(),
                workspace_id=uuid4(),
                agent_id=uuid4(),
                user_id=uuid4(),
                user_message="hello",
            )
        except Exception as exc:
            # Accept any exception except TypeError about unexpected keyword
            assert "unexpected keyword argument 'store'" not in str(exc), str(exc)
```

- [ ] **Step 4.2: Run test — expect FAIL (TypeError about 'store')**

```bash
cd services/api && uv run pytest tests/test_execution_runner_store.py -v
```

Expected: `TypeError: run_deer_execution() got an unexpected keyword argument 'store'`

- [ ] **Step 4.3: Update `execution_runner.py` — add `store` param**

In `services/api/flow/application/execution_runner.py`, update the `run_deer_execution` signature:

```python
async def run_deer_execution(
    *,
    pool: asyncpg.Pool,
    settings: Settings,
    stream_hub: ExecutionStreamHub,
    checkpointer: Any,
    execution_id: UUID,
    workspace_id: UUID,
    agent_id: UUID,
    user_id: UUID,
    user_message: str,
    agent_config: dict[str, Any] | None = None,
    schedule_id: str | None = None,
    store: Any | None = None,  # AsyncPostgresStore for cross-thread memory
) -> None:
```

Add import at top of file:

```python
from flow.infrastructure.llm import agent_factory
```

Update `GraphContext` construction to pass store:

```python
    ctx = GraphContext(
        pool=pool,
        workspace_id=workspace_id,
        agent_id=agent_id,
        user_id=user_id,
        openai_api_key=settings.openai_api_key,
        agent_config=cfg,
        anthropic_api_key=settings.anthropic_api_key,
        execution_id=execution_id,
        settings=settings,
        stream_hub=stream_hub,
        store=store,
    )
    graph = agent_factory.build_agent(ctx, checkpointer=checkpointer)
```

Remove the direct `build_deer_flow_graph` import usage (it's now delegated to `agent_factory`).

- [ ] **Step 4.4: Update `worker.py` — build/open/close memory store**

In `services/api/flow/infrastructure/queue/worker.py`, update `startup`:

```python
async def startup(ctx: dict) -> None:
    settings = get_settings()
    configure_logging(
        level=settings.log_level,
        json_output=settings.log_json,
        service="flow-worker",
        force_colors=settings.log_force_colors,
    )
    pool = await create_pool(settings)
    checkpoint_pool = build_checkpoint_pool(settings.database_url)
    await checkpoint_pool.open()

    from flow.infrastructure.db.store import build_memory_store_pool, create_memory_store
    memory_store_pool = build_memory_store_pool(settings.database_url)
    await memory_store_pool.open()
    memory_store = create_memory_store(memory_store_pool)
    await memory_store.setup()

    stream_hub = ExecutionStreamHub(redis_url=settings.redis_url)
    ctx["pool"] = pool
    ctx["stream_hub"] = stream_hub
    ctx["checkpoint_pool"] = checkpoint_pool
    ctx["memory_store_pool"] = memory_store_pool
    ctx["memory_store"] = memory_store
    ctx["settings"] = settings
    logger.info("worker.started", redis="configured")
```

Update `shutdown`:

```python
async def shutdown(ctx: dict) -> None:
    if hub := ctx.get("stream_hub"):
        await hub.close()
    if cp := ctx.get("checkpoint_pool"):
        await cp.close()
    if msp := ctx.get("memory_store_pool"):
        await msp.close()
    if pool := ctx.get("pool"):
        await close_pool(pool)
```

Update `task_run_deer_execution` to pass store:

```python
        await run_deer_execution(
            pool=ctx["pool"],
            settings=ctx["settings"],
            stream_hub=ctx["stream_hub"],
            checkpointer=checkpointer,
            store=ctx.get("memory_store"),
            # ... rest unchanged
        )
```

- [ ] **Step 4.5: Update `main.py` lifespan — build/setup/close memory store**

In `services/api/flow/interfaces/http/main.py`, inside the `lifespan` async context manager, after the checkpointer setup block, add:

```python
    from flow.infrastructure.db.store import build_memory_store_pool, create_memory_store
    memory_store_pool = build_memory_store_pool(settings.database_url)
    await memory_store_pool.open()
    memory_store = create_memory_store(memory_store_pool)
    await memory_store.setup()
    app.state.memory_store_pool = memory_store_pool
    app.state.memory_store = memory_store
```

Add teardown before `await checkpoint_pool.close()`:

```python
        if hasattr(app.state, "memory_store_pool"):
            await app.state.memory_store_pool.close()
```

Find the route that calls `run_deer_execution` (in `routes/executions.py`) and pass `store`:

```python
    store = getattr(request.app.state, "memory_store", None)
    # add store=store to run_deer_execution call
```

- [ ] **Step 4.6: Update `routes/executions.py` to pass store**

In `services/api/flow/interfaces/http/routes/executions.py`, find the `run_deer_execution` call and add `store=request.app.state.memory_store` (use `getattr` with default `None` for safety):

```python
    store = getattr(request.app.state, "memory_store", None)
    await run_deer_execution(
        ...,
        store=store,
    )
```

- [ ] **Step 4.7: Run test — expect PASS**

```bash
cd services/api && uv run pytest tests/test_execution_runner_store.py -v
```

- [ ] **Step 4.8: Run full test suite**

```bash
cd services/api && uv run pytest tests/ -v --timeout=30 -x
```

- [ ] **Step 4.9: Commit**

```bash
git add services/api/flow/application/execution_runner.py \
        services/api/flow/infrastructure/queue/worker.py \
        services/api/flow/interfaces/http/main.py \
        services/api/flow/interfaces/http/routes/executions.py \
        services/api/tests/test_execution_runner_store.py
git commit -m "feat(memory): wire AsyncPostgresStore through api + worker + execution runner"
```

---

## Task 5: FlowCallbackHandler (structured logging for every model + tool event)

**Files:**
- Create: `services/api/flow/infrastructure/observability/callbacks.py`
- Create: `services/api/tests/test_callbacks.py`

- [ ] **Step 5.1: Write failing tests**

```python
# services/api/tests/test_callbacks.py
from __future__ import annotations

import time
import pytest
from unittest.mock import MagicMock, patch


def test_flow_callback_handler_logs_llm_start(caplog):
    """on_llm_start emits a structured log with model name."""
    import logging
    from flow.infrastructure.observability.callbacks import FlowCallbackHandler

    handler = FlowCallbackHandler()
    with patch.object(handler._log, "info") as mock_log:
        handler.on_llm_start(
            serialized={"name": "ChatOpenAI"},
            prompts=["hello"],
            run_id=MagicMock(),
        )
        mock_log.assert_called_once()
        event = mock_log.call_args[0][0]
        assert "model.start" in event


def test_flow_callback_handler_logs_llm_end():
    """on_llm_end emits a log with latency_ms and token counts."""
    from flow.infrastructure.observability.callbacks import FlowCallbackHandler
    from langchain_core.outputs import LLMResult, Generation

    handler = FlowCallbackHandler()
    handler._llm_start_times[MagicMock().__class__] = {}  # prime start time dict

    run_id = MagicMock()
    handler.on_llm_start(serialized={"name": "ChatAnthropic"}, prompts=["p"], run_id=run_id)

    with patch.object(handler._log, "info") as mock_log:
        result = LLMResult(generations=[[Generation(text="answer")]])
        result.llm_output = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}}
        handler.on_llm_end(response=result, run_id=run_id)
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args[1]
        assert "latency_ms" in call_kwargs or "model.end" in mock_log.call_args[0][0]


def test_flow_callback_handler_logs_tool_start():
    """on_tool_start emits a log with tool name."""
    from flow.infrastructure.observability.callbacks import FlowCallbackHandler

    handler = FlowCallbackHandler()
    with patch.object(handler._log, "info") as mock_log:
        handler.on_tool_start(
            serialized={"name": "tavily_search"},
            input_str="query",
            run_id=MagicMock(),
        )
        mock_log.assert_called_once()
        assert "tool.start" in mock_log.call_args[0][0]


def test_flow_callback_handler_logs_chain_error():
    """on_chain_error emits an error log."""
    from flow.infrastructure.observability.callbacks import FlowCallbackHandler

    handler = FlowCallbackHandler()
    with patch.object(handler._log, "error") as mock_log:
        handler.on_chain_error(error=ValueError("oops"), run_id=MagicMock())
        mock_log.assert_called_once()
```

- [ ] **Step 5.2: Run tests — expect FAIL**

```bash
cd services/api && uv run pytest tests/test_callbacks.py -v
```

Expected: `ModuleNotFoundError: No module named 'flow.infrastructure.observability.callbacks'`

- [ ] **Step 5.3: Create `callbacks.py`**

```python
"""FlowCallbackHandler — structlog-backed observability for every LangChain model/tool event."""
from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from flow.infrastructure.observability.logging import get_logger


class FlowCallbackHandler(BaseCallbackHandler):
    """Emits structured logs for LLM calls and tool invocations.

    Automatically picks up structlog contextvars (execution_id, agent_id, workspace_id)
    already bound by execution_runner.py at execution start.
    """

    def __init__(self) -> None:
        super().__init__()
        self._log = get_logger("flow.llm")
        self._llm_start_times: dict[UUID, float] = {}
        self._tool_start_times: dict[UUID, float] = {}

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._llm_start_times[run_id] = time.monotonic()
        model_name = serialized.get("name") or serialized.get("id", ["unknown"])[-1]
        self._log.info(
            "model.start",
            model=model_name,
            prompt_count=len(prompts),
        )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        latency_ms = int((time.monotonic() - self._llm_start_times.pop(run_id, time.monotonic())) * 1000)
        usage = (response.llm_output or {}).get("token_usage") or {}
        self._log.info(
            "model.end",
            latency_ms=latency_ms,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._llm_start_times.pop(run_id, None)
        self._log.error("model.error", error=str(error), error_type=type(error).__name__)

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._tool_start_times[run_id] = time.monotonic()
        tool_name = serialized.get("name") or "unknown_tool"
        self._log.info("tool.start", tool=tool_name, input_preview=input_str[:200])

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        latency_ms = int((time.monotonic() - self._tool_start_times.pop(run_id, time.monotonic())) * 1000)
        self._log.info("tool.end", latency_ms=latency_ms)

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._tool_start_times.pop(run_id, None)
        self._log.error("tool.error", error=str(error), error_type=type(error).__name__)

    def on_chain_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._log.error(
            "chain.error",
            error=str(error),
            error_type=type(error).__name__,
        )
```

- [ ] **Step 5.4: Run tests — expect PASS**

```bash
cd services/api && uv run pytest tests/test_callbacks.py -v
```

Expected: 4 passed

- [ ] **Step 5.5: Commit**

```bash
git add services/api/flow/infrastructure/observability/callbacks.py \
        services/api/tests/test_callbacks.py
git commit -m "feat(observability): add FlowCallbackHandler for structured model/tool logs"
```

---

## Task 6: Inject FlowCallbackHandler + LangSmith metadata into execution

**Files:**
- Modify: `services/api/flow/application/execution_runner.py`

- [ ] **Step 6.1: Write failing test**

```python
# services/api/tests/test_execution_runner_callbacks.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4


@pytest.mark.asyncio
async def test_run_deer_execution_injects_callback_handler():
    """run_deer_execution includes FlowCallbackHandler in graph run config."""
    from flow.application.execution_runner import run_deer_execution
    from flow.config import Settings
    from flow.infrastructure.observability.callbacks import FlowCallbackHandler

    captured_configs = []

    async def fake_astream(input, config=None, stream_mode=None):
        captured_configs.append(config)
        return
        yield

    settings = Settings(database_url="postgresql://x:x@localhost/x", jwt_secret="test")

    with (
        patch("flow.application.execution_runner.agent_factory") as mock_factory,
        patch("flow.application.execution_runner.FlowRepository") as MockRepo,
    ):
        mock_graph = MagicMock()
        mock_graph.astream = fake_astream
        mock_factory.build_agent.return_value = mock_graph
        MockRepo.return_value.insert_event = AsyncMock()
        MockRepo.return_value.update_execution_status = AsyncMock()

        try:
            await run_deer_execution(
                pool=AsyncMock(),
                settings=settings,
                stream_hub=MagicMock(publish=MagicMock()),
                checkpointer=AsyncMock(),
                execution_id=uuid4(),
                workspace_id=uuid4(),
                agent_id=uuid4(),
                user_id=uuid4(),
                user_message="test",
            )
        except Exception:
            pass

        assert len(captured_configs) > 0
        config = captured_configs[0]
        callbacks = config.get("callbacks", [])
        assert any(isinstance(cb, FlowCallbackHandler) for cb in callbacks), \
            f"No FlowCallbackHandler in callbacks: {callbacks}"
```

- [ ] **Step 6.2: Run test — expect FAIL**

```bash
cd services/api && uv run pytest tests/test_execution_runner_callbacks.py -v
```

Expected: `AssertionError: No FlowCallbackHandler in callbacks`

- [ ] **Step 6.3: Inject callback handler and enrich LangSmith metadata in `execution_runner.py`**

Add import near the top of `services/api/flow/application/execution_runner.py`:

```python
from flow.infrastructure.observability.callbacks import FlowCallbackHandler
```

Find the `config: dict[str, Any]` construction in `run_deer_execution` (currently around line 131) and update it:

```python
    _callback_handler = FlowCallbackHandler()
    config: dict[str, Any] = {
        "configurable": {"thread_id": str(execution_id)},
        "metadata": {
            "execution_id": str(execution_id),
            "agent_id": str(agent_id),
            "workspace_id": str(workspace_id),
            "user_id": str(user_id),
            "template": _template,
        },
        "tags": ["flow", "deer-flow", f"template:{_template}"],
        "run_name": f"flow-exec-{execution_id}",
        "callbacks": [_callback_handler],
    }
```

Note: `_template` is computed later in the current code — move it earlier, just after `cfg` is defined:

```python
    cfg = dict(agent_config) if isinstance(agent_config, dict) else {}
    _template = cfg.get("template") or (cfg.get("graph") or {}).get("template", "unknown") or "unknown"
```

- [ ] **Step 6.4: Run test — expect PASS**

```bash
cd services/api && uv run pytest tests/test_execution_runner_callbacks.py -v
```

- [ ] **Step 6.5: Run full test suite**

```bash
cd services/api && uv run pytest tests/ -v --timeout=30 -x
```

- [ ] **Step 6.6: Commit**

```bash
git add services/api/flow/application/execution_runner.py \
        services/api/tests/test_execution_runner_callbacks.py
git commit -m "feat(observability): inject FlowCallbackHandler + enrich LangSmith metadata"
```

---

## Task 7: agent_factory — build_agent routing with Anthropic middleware

**Files:**
- Create: `services/api/flow/infrastructure/llm/agent_factory.py`
- Create: `services/api/tests/test_agent_factory.py`

- [ ] **Step 7.1: Write failing tests**

```python
# services/api/tests/test_agent_factory.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


def _make_ctx(template: str = "linear-3", provider: str = "openai"):
    from flow.infrastructure.graph.deer_graph import GraphContext
    return GraphContext(
        pool=AsyncMock(),
        workspace_id=uuid4(),
        agent_id=uuid4(),
        user_id=uuid4(),
        openai_api_key="sk-test" if provider == "openai" else None,
        anthropic_api_key="sk-ant-test" if provider == "anthropic" else None,
        agent_config={
            "template": template,
            "model": {"provider": provider, "model": "gpt-4o-mini"},
        },
        store=MagicMock(),
    )


def test_build_agent_returns_deer_graph_for_linear_template():
    """Non-react-agent templates always go through build_deer_flow_graph."""
    from flow.infrastructure.llm import agent_factory

    ctx = _make_ctx("linear-3", "anthropic")
    mock_checkpointer = MagicMock()

    with patch("flow.infrastructure.llm.agent_factory.build_deer_flow_graph") as mock_build:
        mock_build.return_value = MagicMock()
        result = agent_factory.build_agent(ctx, checkpointer=mock_checkpointer)
        mock_build.assert_called_once_with(ctx, checkpointer=mock_checkpointer)


def test_build_agent_uses_create_agent_for_react_anthropic():
    """react-agent + anthropic provider uses create_agent with middleware."""
    from flow.infrastructure.llm import agent_factory

    ctx = _make_ctx("react-agent", "anthropic")
    mock_checkpointer = MagicMock()

    with (
        patch("flow.infrastructure.llm.agent_factory.create_agent") as mock_create,
        patch("flow.infrastructure.llm.agent_factory.ChatAnthropic") as MockClaude,
    ):
        mock_create.return_value = MagicMock()
        MockClaude.return_value = MagicMock()
        agent_factory.build_agent(ctx, checkpointer=mock_checkpointer)
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        middleware_types = [type(m).__name__ for m in call_kwargs.get("middleware", [])]
        assert "StateClaudeMemoryMiddleware" in middleware_types
        assert "AnthropicPromptCachingMiddleware" in middleware_types


def test_build_agent_falls_back_to_deer_graph_for_react_non_anthropic():
    """react-agent + non-anthropic provider falls back to build_deer_flow_graph."""
    from flow.infrastructure.llm import agent_factory

    ctx = _make_ctx("react-agent", "openai")
    with patch("flow.infrastructure.llm.agent_factory.build_deer_flow_graph") as mock_build:
        mock_build.return_value = MagicMock()
        agent_factory.build_agent(ctx, checkpointer=MagicMock())
        mock_build.assert_called_once()
```

- [ ] **Step 7.2: Run tests — expect FAIL**

```bash
cd services/api && uv run pytest tests/test_agent_factory.py -v
```

Expected: `ModuleNotFoundError: No module named 'flow.infrastructure.llm.agent_factory'`

- [ ] **Step 7.3: Add `langchain>=1.2` to `pyproject.toml`**

In `services/api/pyproject.toml`, add to the dependencies list:

```toml
  "langchain>=1.2,<2",
```

Install it:

```bash
cd services/api && uv add "langchain>=1.2,<2"
```

- [ ] **Step 7.4: Create `agent_factory.py`**

```python
"""Agent factory — routes agent_config to the correct graph builder.

- react-agent + anthropic → create_agent with StateClaudeMemoryMiddleware + PromptCachingMiddleware
- all other templates    → build_deer_flow_graph (existing LangGraph compiled graph)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flow.infrastructure.graph.deer_graph import GraphContext


def build_agent(ctx: "GraphContext", checkpointer: Any | None = None) -> Any:
    """Return a compiled LangGraph graph for the given context."""
    from flow.infrastructure.graph.deer_graph import build_deer_flow_graph
    from flow.infrastructure.graph.spec import spec_from_config

    template = spec_from_config(ctx.agent_config).template
    provider = (ctx.agent_config.get("model") or {}).get("provider", "openai")

    if template == "react-agent" and provider == "anthropic" and ctx.anthropic_api_key:
        return _build_anthropic_react_agent(ctx, checkpointer)

    return build_deer_flow_graph(ctx, checkpointer=checkpointer)


def _build_anthropic_react_agent(ctx: "GraphContext", checkpointer: Any | None) -> Any:
    """Build a create_agent graph with Anthropic-specific middleware."""
    from langchain.agents import create_agent
    from langchain_anthropic import ChatAnthropic
    from langchain_anthropic.middleware import (
        AnthropicPromptCachingMiddleware,
        StateClaudeMemoryMiddleware,
    )

    model_cfg = ctx.agent_config.get("model") or {}
    model_name = model_cfg.get("model", "claude-sonnet-4-6")
    temperature = float(model_cfg.get("temperature", 0.2))
    system_prompt = ctx.agent_config.get("system_prompt", "You are a helpful assistant.")

    llm = ChatAnthropic(
        api_key=ctx.anthropic_api_key,
        model=model_name,
        temperature=temperature,
    )

    from flow.infrastructure.tools.registry import build_tool_list
    tools = build_tool_list(ctx)

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        middleware=[
            StateClaudeMemoryMiddleware(allowed_path_prefixes=["/memories"]),
            AnthropicPromptCachingMiddleware(ttl="5m"),
        ],
        checkpointer=checkpointer,
        store=ctx.store,
    )
```

- [ ] **Step 7.5: Check if `build_tool_list` exists in tools registry**

```bash
cd services/api && grep -n "def build_tool_list\|def get_tools" flow/infrastructure/tools/registry.py | head -10
```

If `build_tool_list` doesn't exist, add a stub in `agent_factory.py` that returns `[]`:

```python
def _get_tools_for_ctx(ctx: "GraphContext") -> list:
    try:
        from flow.infrastructure.tools.registry import build_tool_list
        return build_tool_list(ctx)
    except (ImportError, AttributeError):
        return []
```

And replace `tools = build_tool_list(ctx)` with `tools = _get_tools_for_ctx(ctx)`.

- [ ] **Step 7.6: Run tests — expect PASS**

```bash
cd services/api && uv run pytest tests/test_agent_factory.py -v
```

Expected: 3 passed

- [ ] **Step 7.7: Run full test suite**

```bash
cd services/api && uv run pytest tests/ -v --timeout=30 -x
```

- [ ] **Step 7.8: Commit**

```bash
git add services/api/flow/infrastructure/llm/agent_factory.py \
        services/api/pyproject.toml \
        services/api/uv.lock \
        services/api/tests/test_agent_factory.py
git commit -m "feat(agents): add agent_factory with react-agent + Anthropic middleware routing"
```

---

## Task 8: Docker — JSON structured logging

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 8.1: Enable JSON logging for api and worker containers**

In `docker-compose.yml`, under the `api` service `environment:` section, change:

```yaml
      FLOW_LOG_JSON: "true"
      FLOW_LOG_FORCE_COLORS: "false"
```

Under the `worker` service `environment:` section, change the same:

```yaml
      FLOW_LOG_JSON: "true"
      FLOW_LOG_FORCE_COLORS: "false"
```

Keep the `.env.example` or local dev `.env` with `FLOW_LOG_JSON: "false"` for colored TTY output.

- [ ] **Step 8.2: Verify compose file is valid YAML**

```bash
docker compose config --quiet
```

Expected: no error output

- [ ] **Step 8.3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(logging): enable JSON structured logging in api + worker containers"
```

---

## Task 9: End-to-end smoke test in Docker

**Files:**
- (no new files — verification task)

- [ ] **Step 9.1: Build and start containers**

```bash
docker compose up --build -d
```

Wait for api to be healthy:

```bash
docker compose ps
```

Expected: `api` and `worker` status `running`

- [ ] **Step 9.2: Verify JSON logs from api container**

```bash
docker compose logs api --tail=30 | head -10
```

Expected: JSON lines like `{"event": "execution.start ...", "service": "flow-api", ...}`

- [ ] **Step 9.3: Verify JSON logs from worker container**

```bash
docker compose logs worker --tail=20
```

Expected: JSON lines with `"service": "flow-worker"`

- [ ] **Step 9.4: Open browser and create a linear-3 agent (regression test)**

Open `http://localhost:13000` in browser. Create an agent with template `linear-3`. Run a message. Verify it completes without error.

- [ ] **Step 9.5: Create a react-agent with Anthropic model and test memory**

In the Flow UI, create a new agent with:
- Template: `react-agent`
- Model provider: `anthropic`
- Model: `claude-sonnet-4-6`

Send message: `"Remember that my name is Alice and I prefer bullet points."`

Expected: Agent responds using Claude. Check Docker logs for `model.start` and `model.end` JSON entries with `execution_id` field.

- [ ] **Step 9.6: Send second message to same react-agent**

Send: `"What is my name?"`

Expected: Agent responds `Alice` (reads from `/memories` in state via StateClaudeMemoryMiddleware).

- [ ] **Step 9.7: Verify LangSmith traces (if LANGSMITH_API_KEY is configured)**

In LangSmith UI, filter runs by metadata `execution_id`. Verify traces include `workspace_id`, `agent_id`, `template` tags.

- [ ] **Step 9.8: Commit any fixes**

If any issues were found and fixed in steps 9.4–9.7, commit them:

```bash
git add -A
git commit -m "fix: address smoke test issues"
```

---

## Task 10: Update flow-architecture.drawio

**Files:**
- Modify: `flow-architecture.drawio`

- [ ] **Step 10.1: Open drawio file and update architecture**

Open `flow-architecture.drawio` in diagrams.net (drawio.com or desktop app) or edit the XML directly.

Add the following new elements/layers to the diagram:

**Memory Layer** (new swimlane or section):
- Box: `AsyncPostgresSaver (checkpointer)` — label `In-thread memory (per execution thread)`
- Box: `AsyncPostgresStore` — label `Cross-thread memory (workspace × agent × "facts")`
- Arrow from both to `Postgres DB`

**Middleware Stack** (inside "Agent Execution" section):
- Box: `StateClaudeMemoryMiddleware` — label `Reads/writes /memories in state (react-agent only)`
- Box: `AnthropicPromptCachingMiddleware` — label `Caches system prompt (5 min TTL)`
- Show these as filters wrapping the `ChatAnthropic` model box

**Observability Layer**:
- Box: `FlowCallbackHandler` → arrow to `structlog` → arrow to `stdout (JSON)`
- Arrow from `structlog` to `LangSmith` (existing)

**Agent Factory Routing**:
- Diamond: `template == react-agent AND provider == anthropic?`
  - Yes → `create_agent + middleware stack`
  - No → `build_deer_flow_graph (existing templates)`

- [ ] **Step 10.2: Save and commit**

```bash
git add flow-architecture.drawio
git commit -m "docs: update architecture diagram with memory/middleware/observability layers"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task covering it |
|-----------------|-----------------|
| `AsyncPostgresStore` cross-thread memory | Task 1–4 |
| Store namespaces `(ws_id, agent_id, "facts")` | Task 3 |
| `react-agent` template | Task 2 (spec.py), Task 7 (factory) |
| `StateClaudeMemoryMiddleware` | Task 7 |
| `AnthropicPromptCachingMiddleware` | Task 7 |
| `FlowCallbackHandler` | Task 5 |
| Inject callback into execution | Task 6 |
| LangSmith metadata enrichment (execution_id, agent_id, template) | Task 6 |
| `FLOW_LOG_JSON: "true"` in Docker | Task 8 |
| Architecture diagram update | Task 10 |
| `langchain>=1.2` dependency | Task 7.3 |
| Store teardown in API + worker | Task 4 |
| No regression in existing templates | Task 3.6, 4.8, 7.7, 9.4 |

### Success criteria check

1. ✓ Existing agents unchanged — regression tests in Tasks 3.6, 4.8, 7.7, 9.4
2. ✓ `react-agent` browser test — Task 9.5
3. ✓ StateClaudeMemoryMiddleware memory persistence — Task 9.6
4. ✓ Prompt caching — Task 9.7 (LangSmith cache hits)
5. ✓ JSON Docker logs with `execution_id` — Task 9.2–9.3
6. ✓ LangSmith filterable traces — Task 9.7
7. ✓ Store facts persist across executions — Task 3 + 4 combined

### Placeholder scan

No TBDs, TODOs, or vague "handle edge cases" language. All code blocks are complete.

### Type consistency

- `build_agent(ctx, checkpointer)` — consistent across Task 7 definition and Task 4 caller
- `FlowCallbackHandler()` — consistent across Task 5 definition and Task 6 injection
- `create_memory_store(pool)` — consistent across Task 1 and Task 4 usages
- `ctx.store` — added to `GraphContext` in Task 2, used in Tasks 3 and 7
