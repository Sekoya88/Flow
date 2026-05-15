"""Factory for building LangGraph agents with provider-aware routing.

Entry points:
- build_agent_from_ctx(ctx, checkpointer) — routes by template + provider (use this from execution_runner)
- build_agent(provider, model, api_key, ...) — low-level prebuilt react-agent builder
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flow.infrastructure.graph.deer_graph import GraphContext


def _make_model_wrapper(m: Any, inner: Any) -> Any:
    """Build a single wrap_model_call layer. Separate function to capture m+inner correctly."""
    async def _wrapper(msgs: Any) -> Any:
        return await m.wrap_model_call(inner, msgs)
    return _wrapper


def _patch_llm_for_middleware(llm: Any, middleware: list, runtime: Any) -> None:
    """Patch llm._agenerate to chain before_model + wrap_model_call through middleware."""
    if not hasattr(llm, "_agenerate"):
        return

    # Apply tenacity retry first (FlowResilienceMiddleware.patch_llm)
    for m in middleware:
        if hasattr(m, "patch_llm"):
            m.patch_llm(llm)

    # Now wrap the (possibly already-patched) _agenerate with cost + observability
    original = llm._agenerate
    _mw = middleware
    _rt = runtime

    async def _chained(messages: Any, *args: Any, **kwargs: Any) -> Any:
        current = list(messages) if hasattr(messages, "__iter__") else messages

        # before_model hooks — may mutate messages or signal early exit
        for m in _mw:
            result = await m.before_model(current, _rt)
            if isinstance(result, dict) and result.get("jump_to") == "end":
                from langchain_core.messages import AIMessage
                from langchain_core.outputs import ChatGeneration, ChatResult
                return ChatResult(generations=[[ChatGeneration(message=AIMessage(content=""))]])
            elif isinstance(result, list):
                current = result

        # wrap_model_call chain: middleware[0] is outermost, builds inward
        async def _base(msgs: Any) -> Any:
            return await original(msgs, *args, **kwargs)

        invoke = _base
        for m in reversed(_mw):
            invoke = _make_model_wrapper(m, invoke)

        return await invoke(current)

    llm._agenerate = _chained


def _get_llm_for_judge(ctx: "GraphContext") -> Any | None:
    settings = getattr(ctx, "settings", None)
    api_key = settings.openai_api_key if settings else getattr(ctx, "openai_api_key", None)
    if not api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(api_key=api_key, model="gpt-4o-mini", temperature=0)
    except Exception:
        return None


def _make_embed_fn(ctx: "GraphContext"):
    async def _embed(text: str) -> list[float]:
        settings = getattr(ctx, "settings", None)
        api_key = settings.openai_api_key if settings else getattr(ctx, "openai_api_key", None)
        if not api_key:
            return []
        try:
            from flow.infrastructure.llm import embeddings as emb_svc
            results = await emb_svc.embed_texts(api_key=api_key, texts=[text])
            return results[0] if results else []
        except Exception:
            return []
    return _embed


def _build_middleware(ctx: "GraphContext", runtime: Any) -> list:
    from flow.infrastructure.llm.middleware import (
        FlowCostMiddleware,
        FlowMemoryMiddleware,
        FlowObservabilityMiddleware,
        FlowResilienceMiddleware,
    )
    from flow.infrastructure.observability.logging import get_logger

    middleware = []
    judge_llm = _get_llm_for_judge(ctx)

    if ctx.store is not None:
        embed = _make_embed_fn(ctx)
        middleware.append(FlowMemoryMiddleware(store=ctx.store, llm=judge_llm, embed=embed, pool=ctx.pool))

    middleware.append(FlowResilienceMiddleware())

    if judge_llm is not None:
        middleware.append(FlowCostMiddleware(summarize_model=judge_llm))

    bound_logger = get_logger("flow.agent").bind(
        execution_id=str(getattr(ctx, "execution_id", "") or ""),
        agent_id=str(ctx.agent_id),
        workspace_id=str(ctx.workspace_id),
    )
    middleware.append(FlowObservabilityMiddleware(logger=bound_logger))

    return middleware


def build_agent_from_ctx(ctx: "GraphContext", checkpointer: Any | None = None) -> Any:
    """Route to the correct graph builder; wrap react-agent in FlowMiddlewareHarness.

    - react-agent → FlowMiddlewareHarness wrapping create_react_agent(...)
    - all other templates → build_deer_flow_graph (Phase 2 will wrap these too)
    """
    from uuid import UUID

    from flow.infrastructure.graph.spec import spec_from_config
    from flow.infrastructure.llm.middleware.base import FlowMiddlewareHarness, HarnessRuntime

    template = spec_from_config(ctx.agent_config).template
    model_cfg = ctx.agent_config.get("model") or {}
    provider = model_cfg.get("provider", "openai")

    if template == "react-agent":
        from flow.infrastructure.llm.providers import get_chat_model

        api_key = ctx.anthropic_api_key if provider == "anthropic" else ctx.openai_api_key
        model_name = model_cfg.get("model", "gpt-4o-mini")
        temp = float(model_cfg.get("temperature", 0.2))

        # Create LLM first so we can patch it before graph compilation
        llm = get_chat_model(
            {"provider": provider, "model": model_name, "temperature": temp},
            {"openai": api_key if provider == "openai" else None,
             "anthropic": api_key if provider == "anthropic" else None},
        )
        if llm is None:
            return None

        _null_uuid = UUID("00000000-0000-0000-0000-000000000000")
        runtime = HarnessRuntime(
            workspace_id=ctx.workspace_id,
            agent_id=ctx.agent_id,
            user_id=getattr(ctx, "user_id", None) or _null_uuid,
            execution_id=getattr(ctx, "execution_id", None) or _null_uuid,
            thread_id=str(getattr(ctx, "execution_id", None) or "unknown"),
        )
        middleware = _build_middleware(ctx, runtime)

        # Patch LLM for per-call hooks BEFORE create_react_agent compiles it
        _patch_llm_for_middleware(llm, middleware, runtime)

        system_prompt: Any = ctx.agent_config.get("system_prompt")

        # Byte-stability tracking — hash the raw string before any wrapping so
        # the hash is invariant to provider-specific transformations.
        if system_prompt:
            from flow.application.prompt_hash import compute_prompt_hash, record_prompt_hash
            _ph = compute_prompt_hash(system_prompt)
            if _ph and ctx.pool is not None:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(record_prompt_hash(ctx.pool, agent_id=ctx.agent_id, prompt_hash=_ph))
                except RuntimeError:
                    pass

        # Anthropic prompt caching — wrap system prompt in a content block with cache_control
        # so that repeated calls with the same system prompt hit Anthropic's 5-min cache.
        if provider == "anthropic" and system_prompt:
            from langchain_core.messages import SystemMessage
            system_prompt = SystemMessage(content=[{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }])

        raw_graph = build_agent(
            provider=provider,
            model=model_name,
            api_key=api_key,
            llm=llm,
            system_prompt=system_prompt,
            checkpointer=checkpointer,
            store=ctx.store,
            temperature=temp,
        )
        if raw_graph is None:
            return None

        return FlowMiddlewareHarness(raw_graph, middleware=middleware, runtime=runtime)

    from flow.infrastructure.graph.deer_graph import build_deer_flow_graph
    return build_deer_flow_graph(ctx, checkpointer=checkpointer)


def build_agent(
    *,
    provider: str,
    model: str,
    api_key: str | None,
    llm: Any | None = None,
    tools: list[Any] | None = None,
    system_prompt: str | None = None,
    checkpointer: Any | None = None,
    store: Any | None = None,
    temperature: float = 0.2,
):
    """Return a compiled LangGraph react-agent graph.

    Selects the LLM based on *provider*. Returns None if the required API key is absent.
    The returned graph has the same streaming interface as manually compiled graphs.

    Pass *llm* to provide a pre-built (and pre-patched) LLM instance; skips get_chat_model.
    """
    if llm is None:
        from flow.infrastructure.llm.providers import get_chat_model
        llm = get_chat_model(
            {"provider": provider, "model": model, "temperature": temperature},
            {"openai": api_key if provider == "openai" else None,
             "anthropic": api_key if provider == "anthropic" else None},
        )
    if llm is None:
        return None

    from langgraph.prebuilt import create_react_agent

    kwargs: dict[str, Any] = {
        "model": llm,
        "tools": tools or [],
    }
    if system_prompt:
        kwargs["prompt"] = system_prompt
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer
    if store is not None:
        kwargs["store"] = store

    return create_react_agent(**kwargs)
