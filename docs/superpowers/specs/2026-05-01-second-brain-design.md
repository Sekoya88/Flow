# Flow — Second Brain Milestone Design

**Date**: 2026-05-01  
**Status**: Approved  
**Goal**: Make Flow genuinely useful as a personal second brain — upload documents, ask questions, get cited answers.

---

## Target Users & Use Cases

Primary: personal use + knowledge workers  
Secondary: developers (build on top once core experience is solid)

Three use case clusters addressed by this milestone:
- **Second brain** — ingest notes, PDFs, articles; query with citations
- **Personal automation** — recurring agent tasks on ingested knowledge
- **Coding assistant** — layered on top in a future milestone

---

## Core User Journey

The single end-to-end flow this milestone must make flawless:

```
1. First visit → onboarding wizard
   "What do you want to do?" → "Ask questions about my documents"
   → Q&A agent auto-created (linear-3 template, retrieve + memory tools)

2. /knowledge → upload documents
   Drag PDF / paste URL / upload .md .txt .docx
   → ingestion progress visible → "47 chunks indexed ✓"

3. /run → ask a question
   Streamed answer with [1][2] inline citations
   → click citation → see exact chunk + source file

4. Feedback loop
   👍 / 👎 on answer → negative examples stored → improves future retrievals
```

Everything else (proposals, analytics, advanced templates) is out of scope for this milestone.

---

## Phase 1: Onboarding

### Problem
`/onboarding` is generic workspace setup. Users hit a blank dashboard with no guidance on what to do first.

### Solution
Refactor onboarding into a use-case router with inline first-document upload.

**Step 1 — Use case selection**
```
"What do you want to do with Flow?"
  ● Ask questions about my documents   ← default, pre-selected
  ○ Run automated tasks
  ○ Write & execute code
```

**Step 2 — First document upload (if "documents" chosen)**
```
"Upload your first document to get started"
[drag-and-drop zone]
→ ingestion progress shown inline
→ "Done — your assistant is ready" → redirect /run
```

**Auto-created agent on workspace init**
```json
{
  "name": "My Assistant",
  "template": "linear-3",
  "config": {
    "tools": { "retrieve": true, "long_term_memory": true }
  }
}
```

**Invariant**: user has a working, answerable agent before leaving onboarding. No blank state on first dashboard load.

### What doesn't change
Workspace creation logic, JWT flow, workspace_members RBAC. Only onboarding page UI + agent auto-creation added.

---

## Phase 2: Knowledge Ingestion

### Problem
API accepts `{ title, body }` text only. No file upload. Knowledge page is limited to text paste. This blocks the entire second brain use case.

### New API Endpoints

**File upload**
```
POST /knowledge/sources/upload
  Content-Type: multipart/form-data
  Fields: file (PDF, .md, .txt, .docx), workspace_id
  
  - Extracts text: PyMuPDF for PDF, python-docx for .docx, plain read for .md/.txt
  - Enqueues ARQ job: ingest_document_job
  - Returns: { source_id, status: "processing" }
```

**URL crawl**
```
POST /knowledge/sources/crawl
  Body: { url, workspace_id }
  
  - httpx fetch + BeautifulSoup main content extraction
  - Strips nav, footer, scripts
  - Enqueues same ARQ ingestion job
  - Returns: { source_id, status: "processing" }
```

**Ingestion status polling**
```
GET /knowledge/sources/{id}/status
  Returns: { status: processing|ready|failed, chunk_count, error }
```

### Ingestion Pipeline (extend existing)
```
raw text → chunk (512 tokens, 64 overlap)
         → embed (OpenAI text-embedding-3-small)
         → write knowledge_chunks + pgvector
         → write Qdrant (if agentic RAG enabled)
         → update ingest_status = "ready"
```
No new services. Pipeline already exists for text sources — file extraction is the only addition.

### New Dependencies
```toml
# pyproject.toml additions
pymupdf = ">=1.24"        # PDF extraction (pypdf as fallback)
python-docx = ">=1.1"    # .docx extraction
beautifulsoup4 = ">=4.12" # URL crawl HTML parsing
```

### Frontend Changes (`/knowledge` page)
- Drag-and-drop zone (PDF, .md, .txt, .docx, max 20MB)
- URL input tab alongside file drop
- Per-source status badge: spinner → "ready ✓" / "failed ✗"
- Chunk count display: "47 chunks indexed"
- Delete source → cascades to knowledge_chunks (already handled by FK)

---

## Phase 3: Output Quality

### 3a — Citations in Output

**Synthesizer prompt update**
```
Produce your answer with inline citation markers [1], [2], etc.
At the end, list:
Sources:
[1] {source_title} — "{chunk preview, max 120 chars}"
[2] ...
```

**New SSE event type**
```json
{
  "kind": "citations",
  "payload": [
    { "source_id": "uuid", "source_title": "doc.pdf", "chunk_index": 3, "preview": "..." },
    ...
  ]
}
```
Emitted by synthesizer node after answer generation. Persisted to `rag_citations` table (already exists).

**Frontend — new `CitationsPanel` component**
Added below `TokenStream` in `/run` page:
- Numbered list of sources
- Click → expand full chunk text
- Source file name + chunk index shown

### 3b — RAG Quality Fixes

Two changes to `nodes.py` worker retrieval:

1. **Increase retrieval k**: `k=3` → `k=8`, LLM reranker selects top 3. More candidates = better recall without degrading precision.
2. **Query rewrite always-on**: agentic RAG query rewrite node currently conditional — run unconditionally for all queries.

### 3c — Feedback → Retrieval Loop

Infrastructure already exists: `execution_feedback` + `agent_negatives` tables.

**Missing bridge**: when 👎 feedback submitted →
1. Fetch the `rag_citations` for that execution
2. Store `(workspace_id, query, chunk_ids[])` in `agent_negatives`
3. RAG grader prompt augmented with top-5 workspace negatives as few-shot examples:
   ```
   Previously marked unhelpful for similar queries:
   - "{chunk preview}" → [marked irrelevant]
   ```

One prompt change in `flow/infrastructure/graph/nodes.py` grader. No schema changes.

---

## Out of Scope (this milestone)

- Custom agent templates (UI for creating new graph topologies)
- Per-workspace LLM config / BYOK
- Sandbox file I/O
- RAG audit UI (data exists, UI deferred)
- Execution replay
- Collaborative / multi-user features
- Kubernetes / production deployment hardening

---

## Success Criteria

1. User can register, complete onboarding, and have a working Q&A agent **in under 2 minutes**
2. PDF upload → indexed → queryable in **under 30 seconds** for a 10-page PDF
3. Every agent answer in second brain use case includes **at least one citation** with source link
4. 👎 feedback on an execution causes measurably different chunk selection on identical re-query
5. End-to-end flow works with zero developer intervention (no manual API calls, no config editing)

---

## Phase Order & Dependencies

```
Phase 2: File Ingestion (no deps — backend upload endpoint first, 2-3 days)
    ↓
Phase 1: Onboarding     (depends on Phase 2 upload endpoint for inline first-doc upload, 1-2 days)
    ↓
Phase 3: Output Quality (depends on Phase 2 for citation sources to exist, 2-3 days)
```

> Note: Phases are numbered by feature area, not execution order. Build order is 2 → 1 → 3.

Total estimate: **5-8 days** of focused work.
