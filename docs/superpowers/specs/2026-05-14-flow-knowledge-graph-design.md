# Flow — Knowledge Graph Visualization

**Date:** 2026-05-14
**Status:** Approved
**Branch:** to be created

---

## Problem

Flow's operational entities (agents, skills, genomes, executions, system prompts, sub-agents) exist as isolated database rows. There is no way to see how they relate to each other — which agent uses which skills, how a genome evolved across versions, which executions fired which tools. The `kg_nodes`/`kg_edges` tables exist for document knowledge but are unused for Flow's own entities.

Inspired by OpenHuman's principle of transparent, auditable, human-navigable memory, this feature makes every Flow entity a first-class graph citizen.

---

## Scope (Subsystem 3 of 3 — frontend first)

This spec covers **Subsystem 3: Frontend Visualization**. It is the first of three subsystems to implement:

1. **Subsystem 3 (this spec)** — Knowledge Graph page + slide-over panel + Entity Graph Indexer
2. **Subsystem 2 (future)** — Graph traversal context retrieval (replace/augment vector search in `FlowMemoryMiddleware`)
3. **Subsystem 1 (future)** — Full graph traversal API for cross-workspace knowledge search

---

## Architecture

Two frontend surfaces backed by one data layer:

- **`/graph` page** — full-screen, workspace-wide force-directed graph (`react-force-graph-2d`)
- **Slide-over panel** — 1-hop entity subgraph on any entity page (`@xyflow/react`)
- **Entity Graph Indexer** — event-driven hooks writing agents/skills/genomes/executions into existing `kg_nodes`/`kg_edges` on every write
- **3 new API endpoints** — workspace graph, entity subgraph, position persist

No new npm packages. No new database tables. One migration (two columns).

---

## Node Taxonomy

| Type | Shape | Color | Description |
|------|-------|-------|-------------|
| `agent` | Large circle | `#6366f1` (indigo) | Hub node; size = execution count |
| `genome_version` | Triangle | `#f59e0b` (amber) | One per genome snapshot; active = bold border |
| `skill` | Rounded square | `#22d3ee` (cyan) | Size = use_count |
| `system_prompt` | Hexagon | `#a78bfa` (violet) | Linked to genome |
| `sub_agent` | Dashed circle | `#6366f1` (indigo, dashed) | Smaller than agent |
| `execution` | Rectangle | `#10b981` (green) | Opacity fades with age |
| `tool_call` | Diamond | `#f97316` (orange) | Child of execution |
| `knowledge` | Small circle | `#334155` (slate) | Existing memory/chunk nodes |

---

## Edge Types

| Edge | Source → Target | Description |
|------|----------------|-------------|
| `has_skill` | agent → skill | Direct skill assignment |
| `has_genome` | agent → genome_version | Active + archived genomes |
| `prev_version` | genome_version → genome_version | Version chain (dashed edge) |
| `uses_prompt` | genome_version → system_prompt | Prompt used by this genome |
| `orchestrates` | agent → sub_agent | Orchestrator linkage |
| `ran` | agent → execution | Execution history |
| `used_skill` | execution → skill | Skills fired during execution |
| `called` | execution → tool_call | Tool calls made |

---

## Full-Screen Graph Page (`/graph`)

### Layout

- **Top bar**: title "Knowledge Graph" + filter tabs (All / Agents / Skills / Genomes / Executions) + ⌘K search
- **Canvas**: force-directed `react-force-graph-2d` occupying full remaining height
- **Detail panel**: 200px right-side panel, shown on node click
- **Minimap**: bottom-right corner
- **Zoom controls**: bottom-left (+/− /fit)

### Interactions

| Action | Behaviour |
|--------|-----------|
| Filter tab click | Non-matching nodes fade to 10% opacity; edges follow |
| ⌘K search | Fuzzy match on node label; matched node pulses + camera flies to it |
| Single click | Detail panel opens; 1-hop neighbours highlight |
| Double click | Navigate to entity full page (`/agents/[id]`, `/skills/[id]`, etc.) |
| Drag node | x/y persisted to `kg_nodes.position` (debounced 500ms via `PATCH /api/graph/node/{id}/position`) |
| Click linked node in panel | Jump to that node (camera + highlight) |
| "Open page" in panel | Navigate to entity full page |

### Detail Panel Content (per node type)

- **Agent**: name, status, active genome chip (→ jump), skill list (→ jump each), recent executions
- **Skill**: name, version, score, agents using it, recent executions
- **Genome version**: version label, provider/model, status badge, system prompt preview
- **Execution**: id, status, timestamp, skills used, tool calls made
- **System prompt**: first 200 chars, linked genome

### Visual encoding

- Node size: proportional to `use_count` (skills) or execution count (agents); clamped to [8px, 24px]
- Execution opacity: `1.0` for last 7 days, `0.6` for 8–30 days, `0.3` for older
- Active genome: solid bold border; archived: dashed + 60% opacity
- Edge width: `1px` default, `2px` for `has_skill` / `has_genome`

---

## Slide-Over Panel

### Trigger

"Graph" icon button in the header of any agent, skill, or genome page. Opens as a 320px right-side slide-over; main page content dims to 35% opacity.

### Content

- **Header**: entity name + type label + close button
- **Graph**: `@xyflow/react` with dagre top-down layout showing 1-hop subgraph
- **Active genome**: marked with ✦ and bold border; previous versions dashed + faded
- **Footer**: "Expand in graph" (opens `/graph?focus={id}`) + "Full graph page"

### Interactions

- Click any node in the panel → navigate to that entity's page
- "Expand in graph" → opens `/graph` with camera pre-focused on this entity

### Data

Calls `GET /api/graph/entity/{node_type}/{ref_id}` on mount. Returns node + all immediate neighbours + edges between them.

---

## Entity Graph Indexer

**Location:** `services/api/flow/infrastructure/graph/entity_indexer.py`

Event-driven hooks called synchronously on existing write paths (not a background job — graph stays consistent with entity state).

### Hook points

| Event | File to hook | Action |
|-------|-------------|--------|
| `agent_created / agent_updated` | `application/agent_service.py` | Upsert `agent` node; upsert `has_skill` + `has_genome` edges |
| `skill_created / skill_updated` | `application/skill_service.py` or `skill_parser.py` | Upsert `skill` node |
| `genome_activated` | `application/genome_service.py` | Upsert `genome_version` + `system_prompt` nodes; `uses_prompt` + `prev_version` edges |
| `execution_completed` | `application/execution_runner.py` | Upsert `execution` node; `ran` edge (agent→execution); `used_skill` edges derived from `ExecutionEvent` rows with `kind="skill_invoked"` |
| `sub_agent_linked` | agent config write path (when config contains `orchestrator` template with `sub_agent_ids`) | `orchestrates` edge |

### Upsert key

All nodes: `(workspace_id, node_type, ref_id)` — idempotent, safe to call on updates.

---

## API Endpoints

### `GET /api/graph/workspace`

```
Query params:
  ?types=agent,skill,genome   (default: all)
  ?since=7d                   (filters executions only; default 30d)

Response:
  { nodes: KGNode[], edges: KGEdge[] }

Auth: workspace_id from JWT
Limit: max 2000 nodes returned; executions paginated by recency
```

### `GET /api/graph/entity/{node_type}/{ref_id}`

```
Response:
  { node: KGNode, neighbours: KGNode[], edges: KGEdge[] }

Depth: 1-hop only
node_type: agent | skill | genome_version | execution | system_prompt
```

### `PATCH /api/graph/node/{node_id}/position`

```
Body: { x: float, y: float }
Writes to kg_nodes.position (JSONB)
Called on drag-end, debounced 500ms in frontend
```

---

## Schema Changes

One migration. No new tables.

```sql
-- Migration: add ref_id and ref_type columns to kg_nodes
ALTER TABLE kg_nodes ADD COLUMN ref_id VARCHAR;
ALTER TABLE kg_nodes ADD COLUMN ref_type VARCHAR;
CREATE INDEX idx_kg_nodes_ref ON kg_nodes (workspace_id, ref_type, ref_id);

-- New node_type values (no constraint change needed — stored as VARCHAR):
-- 'agent' | 'genome_version' | 'system_prompt' | 'execution' | 'tool_call'

-- New edge_type values (no constraint change needed):
-- 'has_skill' | 'has_genome' | 'prev_version' | 'uses_prompt'
-- 'ran' | 'used_skill' | 'called' | 'orchestrates'
```

---

## Frontend File Structure

```
apps/web/
  app/graph/
    page.tsx                    # /graph route
    components/
      KnowledgeGraph.tsx        # react-force-graph-2d wrapper, filter tabs, search
      NodeDetailPanel.tsx       # right-side detail panel (per node type)
      GraphMinimap.tsx          # minimap overlay
  components/graph/
    EntityGraphPanel.tsx        # slide-over panel (@xyflow/react, dagre)
    EntityGraphButton.tsx       # "Graph" icon trigger button (used in entity headers)
  lib/graph/
    useWorkspaceGraph.ts        # data fetching hook → GET /api/graph/workspace
    useEntityGraph.ts           # data fetching hook → GET /api/graph/entity/{type}/{id}
    graphColors.ts              # node type → color/shape constants
    graphLayouts.ts             # dagre layout config for slide-over
```

---

## Backend File Structure

```
services/api/flow/
  infrastructure/
    graph/
      entity_indexer.py         # upsert helpers for all entity types
  interfaces/
    http/
      routes/
        graph.py                # 3 endpoints
  application/
    agent_service.py            # hook: call entity_indexer on write
    genome_service.py           # hook: call entity_indexer on genome_activated
    execution_runner.py         # hook: call entity_indexer on execution_completed
```

---

## Testing

| File | What it verifies |
|------|-----------------|
| `tests/test_entity_indexer.py` | upsert creates correct node type; edge types correct; idempotent on repeat calls |
| `tests/test_graph_routes.py` | workspace endpoint returns correct nodes/edges; entity endpoint returns 1-hop only; position patch persists |
| `apps/web/__tests__/KnowledgeGraph.test.tsx` | filter tabs fade non-matching nodes; search highlights correct node; detail panel shows correct content per node type |
| `apps/web/__tests__/EntityGraphPanel.test.tsx` | panel opens on button click; displays correct neighbours; "expand" navigates correctly |

---

## Success Criteria

1. `/graph` loads and renders all workspace agents, skills, and active genomes within 2s for a workspace with ≤50 agents
2. Clicking an agent node shows its skills, active genome, and last 5 executions in the detail panel
3. Slide-over panel opens on any agent/skill page and shows correct 1-hop subgraph
4. Dragging a node and refreshing the page restores the node to its dragged position
5. Entity Graph Indexer: creating a new agent and opening `/graph` shows the agent as a node without manual refresh
6. Filter tabs: selecting "Skills" hides all non-skill nodes; selecting "All" restores them
7. All 4 test files pass; no regressions in existing test suite

---

## Out of Scope (Subsystem 2 + 3)

- Graph traversal for LLM context (Subsystem 2) — separate spec
- Cross-workspace knowledge search (Subsystem 1) — separate spec
- 3D graph view (deprioritised — `react-force-graph-3d` installed but not used here)
- Editing entities inline from the graph (read + navigate only)
