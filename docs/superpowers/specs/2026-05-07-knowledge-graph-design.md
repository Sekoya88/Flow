# Knowledge Graph — Design Spec

**Date:** 2026-05-07  
**Status:** Approved

---

## Goal

Build an interactive Obsidian-style knowledge graph inside Flow. Users ingest notes from their Obsidian vault (upload, Local REST API, or filesystem sync), a LangGraph agentic pipeline extracts entities and relations, and the result is a force-directed graph they can explore and query with a conversational agent.

## Architecture Overview

Three bounded subsystems connected through shared Postgres storage:

1. **Ingest pipeline** — Obsidian connectors → parser → LangGraph categorization agent → Postgres (`kg_nodes`, `kg_edges`)
2. **Graph engine** — NetworkX loaded on demand from Postgres for traversal (PageRank, shortest path, community detection). No external graph DB.
3. **Frontend** — ReactFlow force-directed graph (`/graph` page) + right-panel query agent with SSE streaming. Colors use Flow design system tokens.

**Why NetworkX over Neo4j:** Obsidian vaults are personal, max ~50k notes. NetworkX in memory covers all graph algorithms (Louvain clustering, PageRank, shortest path) without additional infrastructure.

---

## Data Model

### Domain Entities (Pydantic)

**File:** `services/api/flow/domain/knowledge_graph/entities.py`

```python
class NodeType(str, Enum):
    NOTE      = "note"      # .md file from Obsidian
    CONCEPT   = "concept"   # LLM-extracted entity (person, tech, idea)
    TOPIC     = "topic"     # LLM-assigned category (emergent, auto-created)
    QUERY     = "query"     # agent question node (for query history in graph)

class EdgeType(str, Enum):
    LINKS_TO      = "links_to"       # Obsidian [[wikilink]]
    TAGGED_WITH   = "tagged_with"    # Obsidian #tag
    MENTIONS      = "mentions"       # entity extracted from note body
    SIMILAR_TO    = "similar_to"     # cosine similarity > 0.85
    BELONGS_TO    = "belongs_to"     # note → topic
    REFERENCED_BY = "referenced_by"  # query node → source notes used

class KGNode(BaseModel):
    id: UUID
    workspace_id: UUID
    label: str
    node_type: NodeType
    source_path: str | None      # vault-relative path for NOTE nodes
    content_hash: str | None     # SHA-256 of raw content (for dedup)
    summary: str | None          # LLM-generated, ≤200 chars
    embedding: list[float] | None  # 1536-dim OpenAI embedding
    metadata: dict[str, Any]     # tags, frontmatter YAML, page_num, etc.
    cluster_id: int | None       # Louvain community ID
    pagerank: float              # NetworkX PageRank score
    created_at: datetime
    updated_at: datetime

class KGEdge(BaseModel):
    id: UUID
    workspace_id: UUID
    source_id: UUID
    target_id: UUID
    edge_type: EdgeType
    weight: float                # 0.0–1.0
    metadata: dict[str, Any]
    created_at: datetime
```

### Pydantic Schemas (API layer)

**File:** `services/api/flow/interfaces/http/schemas_kg.py`

```python
class KGNodeOut(BaseModel):
    id: str
    label: str
    node_type: str
    summary: str | None
    source_path: str | None
    cluster_id: int | None
    pagerank: float
    metadata: dict[str, Any]

class KGEdgeOut(BaseModel):
    id: str
    source_id: str
    target_id: str
    edge_type: str
    weight: float

class KGGraphOut(BaseModel):
    nodes: list[KGNodeOut]
    edges: list[KGEdgeOut]
    cluster_count: int

class KGIngestObsidianIn(BaseModel):
    workspace_id: UUID
    base_url: str                # e.g. http://localhost:27123
    api_key: str
    vault_path: str = "/"

class KGQueryIn(BaseModel):
    workspace_id: UUID
    question: str
    stream: bool = True
```

### Postgres Schema

**Migration:** `services/api/flow/infrastructure/db/migrations.py` (appended)

```sql
CREATE TABLE kg_nodes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    label         TEXT NOT NULL,
    node_type     TEXT NOT NULL CHECK (node_type IN ('note','concept','topic','query')),
    source_path   TEXT,
    content_hash  TEXT,
    summary       TEXT,
    embedding     vector(1536),
    metadata      JSONB NOT NULL DEFAULT '{}',
    cluster_id    INT,
    pagerank      FLOAT NOT NULL DEFAULT 0.0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, label, node_type)
);

CREATE TABLE kg_edges (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    source_id     UUID NOT NULL REFERENCES kg_nodes(id) ON DELETE CASCADE,
    target_id     UUID NOT NULL REFERENCES kg_nodes(id) ON DELETE CASCADE,
    edge_type     TEXT NOT NULL,
    weight        FLOAT NOT NULL DEFAULT 1.0,
    metadata      JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, target_id, edge_type)
);

CREATE INDEX ON kg_nodes USING ivfflat (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;
CREATE INDEX ON kg_nodes (workspace_id, node_type);
CREATE INDEX ON kg_edges (workspace_id, source_id);
CREATE INDEX ON kg_edges (workspace_id, target_id);
```

---

## Subsystem 1: Ingest Pipeline

### Obsidian Connectors

**File:** `services/api/flow/application/kg_connectors.py`

Three connectors share the same output type:

```python
class ObsidianDocument(BaseModel):
    filename: str          # vault-relative path, e.g. "AI/LangGraph.md"
    raw_content: str       # raw Markdown
    source: Literal["upload", "api", "sync"]
```

- **`parse_upload(files: list[UploadFile]) -> list[ObsidianDocument]`** — reads multipart `.md` files
- **`fetch_from_obsidian_api(base_url, api_key, vault_path) -> list[ObsidianDocument]`** — calls Obsidian Local REST API (`GET /vault/{path}` to list, `GET /vault/{path}/{file}` to fetch)
- **`sync_from_path(vault_path, since) -> list[ObsidianDocument]`** — walks filesystem, filters by `mtime > since`

### Obsidian Parser

**File:** `services/api/flow/application/kg_parser.py`

```python
class ParsedNote(BaseModel):
    filename: str
    title: str                   # H1 header or filename stem
    frontmatter: dict[str, Any]  # YAML between --- delimiters
    tags: list[str]              # #tag occurrences in body
    wikilinks: list[str]         # [[Target Note]] resolved labels
    body: str                    # cleaned Markdown, no frontmatter
    content_hash: str            # SHA-256 of raw_content

def parse_obsidian_note(doc: ObsidianDocument) -> ParsedNote: ...
```

Implementation details:
- Frontmatter: regex `^---\n(.*?)\n---` + `yaml.safe_load`
- Tags: regex `#([a-zA-Z][a-zA-Z0-9_/-]*)` excluding code blocks
- Wikilinks: regex `\[\[([^\]|]+)(?:\|[^\]]+)?\]\]` → extract label

### LangGraph Ingestion Graph

**File:** `services/api/flow/application/kg_ingestion_graph.py`

```python
class IngestionState(TypedDict):
    workspace_id: str
    document: ObsidianDocument
    parsed: ParsedNote | None
    is_duplicate: bool
    entities: list[str]           # ≤10 concepts from LLM
    topic: str                    # category string
    summary: str                  # ≤200 chars
    embedding: list[float]
    note_node_id: str | None
    error: str | None
```

**Nodes (in order):**

1. **`parse_note`** — calls `parse_obsidian_note`, returns `ParsedNote`
2. **`check_duplicate`** — queries `kg_nodes` by `(workspace_id, content_hash)`. Sets `is_duplicate=True` if found and unchanged.
3. **`extract_entities`** — gpt-4o-mini with structured output:
   ```
   System: "Extract ≤10 key concepts, people, technologies, or ideas from this text.
            Return JSON: {"entities": ["string", ...]}"
   Human: {parsed.body[:3000]}
   ```
4. **`assign_topic`** — gpt-4o-mini with existing topic list in context:
   ```
   System: "Assign one topic category to this note. Prefer existing topics for coherence.
            Existing: {existing_topics}. If none fit, create a short new one.
            Return JSON: {"topic": "string"}"
   Human: {parsed.title}\n\n{parsed.body[:1000]}
   ```
5. **`embed_and_summarize`** — single gpt-4o-mini call for summary (≤200 chars) + OpenAI embedding of `title + body[:2000]`
6. **`upsert_nodes`** — upsert `kg_nodes` for: the note itself + each entity + the topic. Uses `ON CONFLICT (workspace_id, label, node_type) DO UPDATE`.
7. **`build_edges`** — creates edges:
   - note → topic: `BELONGS_TO` (weight 1.0)
   - note → each entity: `MENTIONS` (weight 0.8)
   - note → each resolved wikilink: `LINKS_TO` (weight 1.0)
   - note → each tag: `TAGGED_WITH` (weight 0.7)
   - note → existing notes with cosine distance < 0.15 (similarity > 0.85): `SIMILAR_TO` (weight = 1 − cosine_dist), max 5 per note
8. **`recompute_graph_metrics`** — loads full workspace graph from Postgres into NetworkX DiGraph, runs:
   - `nx.pagerank(G)` → updates `kg_nodes.pagerank`
   - `community.best_partition(G.to_undirected())` (python-louvain) → updates `kg_nodes.cluster_id`
   - Writes back via bulk UPDATE

**Conditional routing:**
```python
def route_after_duplicate_check(state) -> str:
    return END if state["is_duplicate"] else "extract_entities"
```

**Graph wiring:**
```
parse_note → check_duplicate → [route] → extract_entities → assign_topic
    → embed_and_summarize → upsert_nodes → build_edges → END
```

**Batch recompute:** `recompute_graph_metrics` is NOT called per-note inside the graph. Instead, the ingest route calls it once after all documents in a batch complete. This avoids O(N²) NetworkX reloads during bulk vault imports.

### Graph Engine (NetworkX layer)

**File:** `services/api/flow/infrastructure/kg/graph_engine.py`

```python
class KGGraphEngine:
    def __init__(self, pool: asyncpg.Pool): ...

    async def load_graph(self, workspace_id: UUID) -> nx.DiGraph:
        """Load full graph from Postgres into NetworkX. Called per-request, cheap for <50k nodes."""

    def find_shortest_path(self, G: nx.DiGraph, source_label: str, target_label: str) -> list[str]:
        """Returns sequence of node labels. Raises NetworkXNoPath if disconnected."""

    def get_subgraph(self, G: nx.DiGraph, center_label: str, depth: int = 2) -> nx.DiGraph:
        """BFS ego graph of radius=depth around center node."""

    def get_cluster_nodes(self, G: nx.DiGraph, cluster_id: int) -> list[str]:
        """All node labels in a given Louvain cluster, sorted by pagerank desc."""
```

---

## Subsystem 2: Query Agent

### LangGraph Query Graph

**File:** `services/api/flow/application/kg_query_graph.py`

```python
class QueryState(TypedDict):
    workspace_id: str
    question: str
    messages: list[BaseMessage]
    intent: Literal["factual", "relational", "exploratory", "hybrid"]
    tool_calls: list[dict]        # streamed to frontend
    graph_path: list[str] | None  # node labels for path highlight
    cited_node_ids: list[str]     # node IDs to highlight in viz
    answer: str | None
```

**Nodes:**

1. **`classify_intent`** — gpt-4o-mini classifies question intent:
   - `factual` → "what is X", "tell me about X"
   - `relational` → "how does X relate to Y", "path between X and Y"
   - `exploratory` → "what do I know about X", "explore X", "summarize my notes on X"
   - `hybrid` → any combination

2. **`react_agent`** — standard ReAct loop (LangGraph `create_react_agent`) with 5 tools. Tools are closures built at graph-construction time with `pool: asyncpg.Pool` and `engine: KGGraphEngine` injected via `build_kg_query_graph(pool, engine, workspace_id)` factory.

```python
@tool
async def vector_search(query: str, k: int = 6) -> list[dict]:
    """Semantic search over kg_nodes embeddings. Returns label, summary, node_type, source_path."""

@tool
async def get_node_content(node_id: str) -> str:
    """Full Markdown body of a NOTE node."""

@tool
async def find_path(source_label: str, target_label: str) -> dict:
    """Shortest path between two nodes. Returns {'path': [...labels], 'edges': [...types]}."""

@tool
async def explore_subgraph(node_label: str, depth: int = 2) -> dict:
    """BFS subgraph of radius=depth. Returns {'nodes': [...], 'edges': [...]}."""

@tool
async def get_cluster_summary(cluster_id: int) -> dict:
    """All nodes in a Louvain cluster, sorted by pagerank. Returns {'nodes': [...label, pagerank]}."""
```

3. **`synthesize`** — final gpt-4o synthesis from gathered context:
   - Builds answer with path explanation in natural language if `find_path` was called
   - Includes `cited_node_ids` for frontend highlighting

**Routing:** `classify_intent` → `react_agent` (all intents use same ReAct loop, intent is injected into system prompt to bias tool selection)

### SSE Events

```
event: kg_tool_call   {"tool": "find_path", "args": {"source": "A", "target": "B"}}
event: kg_path        {"nodes": ["A","B","C"], "edges": ["mentions","links_to"]}
event: kg_highlight   {"node_ids": ["uuid1","uuid2","uuid3"]}
event: kg_answer      {"text": "...", "citations": [{"label":"...", "source_path":"..."}]}
event: kg_done        {}
```

---

## Subsystem 3: Frontend

### New page: `/graph`

**File:** `apps/web/src/app/(app)/graph/page.tsx`

Two-column layout (mirrors the mockup):
- Left: `KnowledgeGraphCanvas` (ReactFlow force-directed, full height)
- Right: `GraphQueryPanel` (360px fixed, tabs: Query / Import)

Added to `AppShell` nav: `{ href: "/graph", label: "Graph", icon: Network }`

### Components

**`apps/web/src/components/kg/KnowledgeGraphCanvas.tsx`**
- Uses `@xyflow/react` with custom node types per `NodeType`
- D3 force simulation via `d3-force` for layout (installed, already a transitive dep)
- Node colors map to cluster_id via a deterministic palette (indigo/teal/amber/pink matching Flow's palette)
- On agent `kg_highlight` SSE event: highlighted node IDs get a glow ring via node style update
- On agent `kg_path` SSE event: path edge gets animated stroke
- Hover tooltip shows: label, summary, tags, pagerank, link count

**`apps/web/src/components/kg/GraphQueryPanel.tsx`**
- Query tab: chat interface with SSE streaming, `ToolCallRow` (reuses `ToolCallLog` pattern), `PathViz` inline component, citations list
- Import tab: upload dropzone (multipart POST), Obsidian API connection form, sync button with progress bar

**`apps/web/src/components/kg/PathViz.tsx`**
- Horizontal pill chain: `Node → edge-type → Node → edge-type → Node`
- Uses Flow brand colors for node pills

### API client calls

```typescript
// GET /api/v1/kg/graph?workspace_id=X
// POST /api/v1/kg/ingest/upload     (multipart)
// POST /api/v1/kg/ingest/obsidian   (JSON)
// POST /api/v1/kg/sync              (JSON)
// POST /api/v1/kg/query             (SSE stream)
// GET  /api/v1/kg/graph/node/:id    (node detail + neighbors)
// DELETE /api/v1/kg/node/:id
```

---

## API Routes

**File:** `services/api/flow/interfaces/http/routes/kg.py`

```
POST   /api/v1/kg/ingest/upload    multipart .md files
POST   /api/v1/kg/ingest/obsidian  {base_url, api_key, vault_path, workspace_id}
POST   /api/v1/kg/sync             {vault_path, workspace_id}
GET    /api/v1/kg/graph            ?workspace_id=X → KGGraphOut
GET    /api/v1/kg/graph/node/{id}  node detail + 1-hop neighbors
DELETE /api/v1/kg/node/{id}        ?workspace_id=X
POST   /api/v1/kg/query            {question, workspace_id, stream:true} → SSE
```

---

## Repo Methods

**`services/api/flow/infrastructure/persistence/repo.py`** — additions:

```python
async def upsert_kg_node(self, workspace_id, label, node_type, **fields) -> UUID
async def get_kg_node_by_label(self, workspace_id, label, node_type) -> Record | None
async def list_kg_nodes(self, workspace_id) -> list[Record]
async def list_kg_edges(self, workspace_id) -> list[Record]
async def upsert_kg_edge(self, workspace_id, source_id, target_id, edge_type, weight, metadata) -> UUID
async def bulk_update_kg_pagerank(self, updates: list[tuple[UUID, float]]) -> None
async def bulk_update_kg_cluster(self, updates: list[tuple[UUID, int]]) -> None
async def vector_search_kg(self, workspace_id, embedding, k=6) -> list[Record]
async def delete_kg_node(self, workspace_id, node_id) -> bool
async def list_kg_topics(self, workspace_id) -> list[str]
```

---

## File Map

```
services/api/flow/
  domain/
    knowledge_graph/
      entities.py          ← KGNode, KGEdge, NodeType, EdgeType (Pydantic)
  application/
    kg_connectors.py       ← ObsidianDocument + 3 connector functions
    kg_parser.py           ← ParsedNote + parse_obsidian_note
    kg_ingestion_graph.py  ← IngestionState + LangGraph ingestion flow
    kg_query_graph.py      ← QueryState + 5 tools + LangGraph query agent
  infrastructure/
    kg/
      graph_engine.py      ← KGGraphEngine (NetworkX load/traversal)
    persistence/
      repo.py              ← 10 new kg_* methods (appended)
    db/
      migrations.py        ← kg_nodes + kg_edges tables (appended)
  interfaces/
    http/
      routes/
        kg.py              ← 7 endpoints
      schemas_kg.py        ← KGNodeOut, KGEdgeOut, KGGraphOut, KGIngestObsidianIn, KGQueryIn

apps/web/src/
  app/(app)/
    graph/
      page.tsx             ← /graph page (two-column layout)
  components/
    kg/
      KnowledgeGraphCanvas.tsx  ← ReactFlow + D3 force layout + highlight logic
      GraphQueryPanel.tsx       ← chat + import tabs
      PathViz.tsx               ← horizontal pill chain for path display
```

---

## Error Handling

- **Duplicate ingest**: `check_duplicate` node short-circuits the graph via `END`, no re-embedding
- **Obsidian API unreachable**: connector raises `KGConnectorError`, route returns 502 with message
- **No path found**: `find_path` tool returns `{"path": null, "message": "No path found"}`, agent explains in natural language
- **Missing embedding**: nodes without embedding (e.g. TOPIC nodes with short labels) skip `SIMILAR_TO` edge creation
- **NetworkX empty graph**: `load_graph` with 0 nodes returns empty DiGraph, query agent falls back to pure vector search

---

## Testing

- `tests/test_kg_parser.py` — parse_obsidian_note: frontmatter, wikilinks, tags, edge cases (no frontmatter, nested headers)
- `tests/test_kg_connectors.py` — sync_from_path: mock filesystem, verify dedup by hash
- `tests/test_kg_ingestion.py` — full ingestion graph with mocked LLM + repo, verify node/edge counts
- `tests/test_kg_graph_engine.py` — find_shortest_path, get_subgraph, get_cluster_nodes with synthetic NetworkX graph
- `tests/test_kg_query_agent.py` — query graph with mocked tools, verify SSE event sequence

---

## Dependencies

New Python packages:
- `python-louvain` (community detection, `community.best_partition`)
- `networkx` (graph algorithms — likely already installed as transitive dep)
- `httpx` (already installed — used for Obsidian API calls)
- `python-multipart` (already installed — for file upload)

New frontend packages: none — `@xyflow/react` and `d3-*` types already present.
