# Flow — Development Roadmap

*Inspired by [OpenHuman](https://github.com/tinyhumansai/openhuman) — a local-first personal AI with rigorous preference learning, tiered agent execution, and transparent memory.*

Last updated: 2026-05-14  
Branch convention: `feat/<subsystem-slug>`

---

## Completed

| Feature | Branch | Notes |
|---------|--------|-------|
| Skill versioning (append-only INT) | `feat/agent-genome-versionning` | migrations 0004/0006 |
| Agent genome (snapshot/activate/load) | `feat/agent-genome-versionning` | migrations 0008/0010 |
| Golden set evaluation | `feat/agent-genome-versionning` | migrations 0009/0011 |
| AsyncPostgresStore (cross-thread memory) | `feat/agent-genome-versionning` | `infrastructure/db/store.py` |
| FlowMiddlewareHarness (memory/resilience/cost/observability) | `feat/agent-genome-versionning` | `infrastructure/llm/middleware/` |
| Knowledge Graph — entity indexer + API + frontend | `feat/knowledge-graph` | entity nodes in kg_nodes, /graph page, slide-over panel |

---

## Subsystem A — User Profile & Preference System

**Inspiration:** OpenHuman's `PROFILE.md` + personalization cache (6 facet classes, scored with per-class decay half-lives, editable by user).

**What it builds:**  
Persistent user preference profile stored per `(workspace_id, user_id)`. Typed facets: `style`, `identity`, `tooling`, `veto`, `goal`, `channel`. Each facet has a score (0–1) and a decay half-life. `FlowMemoryMiddleware.before_agent` injects the active profile as a `SystemMessage` block before the planner. Users can view/edit/pin/forget facets in the UI.

**Why:** Every agent run improves automatically. The agent knows the user prefers concise answers, uses Python, wants citations, etc. — without the user repeating themselves.

**Depends on:** AsyncPostgresStore ✅, FlowMemoryMiddleware ✅  
**Status:** Not started  
**Spec:** `docs/superpowers/specs/2026-05-14-flow-user-profile-design.md` *(to be written)*

---

## Subsystem B — Byte-stable System Prompts + Fork Subagents

**Inspiration:** OpenHuman's prefix-cache invariant (byte-stable system prompts as a runtime constraint) + fork mode (child agent replays parent prefix exactly for cache reuse).

**What it builds:**  
System prompt stored as a versioned artifact pinned to genome version. Same genome = byte-identical system prompt = Anthropic/OpenAI prefix cache hit on every run. Fork subagent mode: spawning a sub-agent replays the parent's exact system prompt prefix, inheriting the cache hit. This makes subagent spawning nearly free in latency terms.

**Why:** Direct cost and latency reduction on every run. Pairs tightly with genome versioning already in place.

**Depends on:** Genome versioning ✅, agent_factory ✅  
**Status:** Not started  
**Spec:** *(to be written)*

---

## Subsystem C — Per-agent Tool Visibility Scoping

**Inspiration:** OpenHuman's runtime tool registry vs. narrowed model-visible set. Subagents inherit filtered tool scopes from parent.

**What it builds:**  
Agent config gains a `tool_scope` field: list of allowed tool names (or `"*"` for all). `build_agent_from_ctx` passes only the declared tools to the LLM call, even if more are registered. Orchestrator agents can spawn sub-agents with a strict subset of their own scope. UI shows per-agent tool list with toggle controls.

**Why:** Prevents agents from calling irrelevant tools (wasted tokens, hallucinated calls). Enables least-privilege agent design.

**Depends on:** agent_factory ✅  
**Status:** Not started  
**Spec:** *(to be written)*

---

## Subsystem D — Graph Traversal Context Retrieval

**Inspiration:** Flow's own KG roadmap (Subsystem 2), validated by OpenHuman's memory-retrieval architecture.

**What it builds:**  
Replace (or augment) the planner's pure vector search with 1–2 hop KG traversal. Starting from the top vector-match node, walk edges to pull in related entities (skills used by the same agent, previous executions of the same skill, genomes that referenced this system prompt). Richer, relationship-aware context passed to the planner.

**Why:** Vector similarity finds topically similar nodes. Graph traversal finds *structurally related* nodes — a fundamentally different retrieval signal that complements embedding search.

**Depends on:** Knowledge Graph ✅, AsyncPostgresStore ✅  
**Status:** Not started  
**Spec:** *(to be written)*

---

## Subsystem E — Hierarchical Memory Compression

**Inspiration:** OpenHuman's Memory Tree — recent facts compressed into ≤3k-token Markdown summaries, folded into a hierarchical SQLite-backed tree with scored pruning.

**What it builds:**  
A background job (or lazy `before_agent` trigger) that compresses aging `facts` in `AsyncPostgresStore` into weekly summaries, then monthly summaries. Low-scored facts (below a configurable threshold) are pruned. The planner receives a mix of recent raw facts + compressed summaries rather than an unbounded flat list.

**Why:** As agents accumulate hundreds of runs, raw facts overflow context. Hierarchical compression keeps memory useful without token blowout.

**Depends on:** AsyncPostgresStore ✅, User Profile System (A) — memory and profile share the store  
**Status:** Not started  
**Spec:** *(to be written)*

---

## Dependency Graph

```
Completed infra
  └── A (User Profile)
        └── E (Hierarchical Compression)   [shares store with A]
  └── B (Byte-stable Prompts)              [builds on genome]
  └── C (Tool Visibility Scoping)          [builds on agent_factory]
  └── D (Graph Traversal Context)          [builds on KG + store]
```

Suggested order: **A → B → D → C → E**

- A first: highest per-run impact, unlocks E later
- B second: cost/latency win, natural genome extension
- D third: extends the KG just built while it's fresh
- C fourth: precision improvement, lower urgency
- E last: most complex, requires A's store to be populated

---

## Active Spec

**Subsystem A** is next — spec in progress at `docs/superpowers/specs/YYYY-MM-DD-flow-user-profile-design.md`.
