# Flow — User Experience Guide

Complete setup and usage guide for the three Flow clients: **Web**, **FlowIsland** (Mac notch), and the **Chrome Extension**.

---

## 1. Prerequisites

| Requirement | Version | Notes |
| ----------- | ------- | ----- |
| Docker + Docker Compose | latest | For the backend stack |
| Node.js | 20+ | Chrome extension build only |
| Xcode | 15+ | FlowIsland only, Mac required |
| OpenAI API key | — | Powers embeddings + all LLM calls |

---

## 2. Backend (required by all clients)

### 2.1 Configure environment

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```bash
FLOW_OPENAI_API_KEY=sk-...
FLOW_JWT_SECRET=$(openssl rand -hex 32)   # run this and paste the output
```

Optional but recommended:

```bash
# Hybrid RAG with Qdrant (BM25 + dense, fused via RRF)
FLOW_QDRANT_URL=http://localhost:16333
FLOW_QDRANT_COLLECTION=flow_knowledge
FLOW_AGENTIC_RAG_ENABLED=true

# Obsidian vault sync (mount your local vault)
FLOW_OBSIDIAN_VAULT_PATH=/Users/you/Documents/ObsidianVault

# Research paper search via Tavily
FLOW_TAVILY_API_KEY=tvly-...

# LangSmith traces
FLOW_LANGSMITH_API_KEY=lsv2_pt_...
FLOW_LANGSMITH_PROJECT=flow-local
```

### 2.2 Obsidian vault mount

If you want Export to Obsidian to write files to your real vault, add a volume in `docker-compose.yml` under the `api` service:

```yaml
services:
  api:
    volumes:
      - ${FLOW_OBSIDIAN_VAULT_PATH}:/vault
```

The API writes to `/vault` inside the container, which maps to your vault on disk.

### 2.3 Start the stack

```bash
docker compose up --build
# Or after pulling new code:
make update
```

Services started:

| Host | Container | Purpose |
| ---- | --------- | ------- |
| <http://localhost:13000> | `web` | Next.js UI |
| <http://localhost:18000> | `api` | FastAPI REST + SSE |
| `localhost:55432` | `db` | PostgreSQL |
| `localhost:16379` | `redis` | ARQ task queue |
| <http://localhost:16333> | `qdrant` | Vector store (optional) |

---

## 3. Web app

### First login

1. Open <http://localhost:13000>
2. Click **Sign up** → create an account
3. Complete the onboarding questionnaire (style, domain, tooling preferences)
4. You land on the main dashboard

### Key pages

| Page | Path | What to do |
| ---- | ---- | ---------- |
| **Run** | `/run` | Chat with an agent — streamed answers with citations |
| **Knowledge** | `/knowledge` | Upload PDF/DOCX/MD/TXT or paste a URL to ingest |
| **Research** | `/research` | Daily arXiv + HuggingFace digest, AI-scored papers |
| **Graph** | `/graph` | Interactive knowledge graph — click nodes, query in natural language |
| **Agents** | `/agents` | Create/edit agents, configure tools and genome versions |
| **Skills** | `/skills` | Browse and assign reusable skill instructions |
| **Memory** | `/memory` | View long-term facts stored across sessions |
| **Settings** | `/settings` | Profile preferences, CV import |

### Research digest workflow

1. Go to **Research** → click **Configure** to set arXiv categories and relevance threshold
2. Click **Run now** — the worker fetches today's arXiv + HuggingFace papers and scores them
3. Select papers → click **Synthesize** for an AI cross-paper synthesis
4. Select papers → click **Export to Obsidian** to write `.md` files to your vault
5. Select papers → click **Embed as Knowledge** to push them into Qdrant for agent RAG

### Graph query

Open `/graph` → click **Query** (top right) → type a natural language question.

The system runs vector search + keyword fallback across all 100+ node types (papers, skills, agents, traces). Path queries work too: *"how does X relate to Y"*.

---

## 4. FlowIsland — macOS notch client

FlowIsland lives in the MacBook notch. It shows a live pill that expands on hover.

### Build and run

1. Open `apps/mac/FlowIsland.xcodeproj` in Xcode
2. Select your Mac as the run target
3. In `AppDelegate.swift`, confirm the API URL points to your running backend:

```swift
// WebSocketClient.swift — default is ws://localhost:18000
```

4. Hit **Run** (⌘R) — the app appears in the notch area, no Dock icon
5. Hover over the notch pill to expand the panel

### What it shows

- **Active agent** — current running agent and live status
- **Skill graph** — Obsidian-style force graph of your skills and connections
- **Agent picker** — switch between agents
- **Knowledge tab** — memory and knowledge items linked to the active agent
- **Runs** — recent execution history

### Permissions

FlowIsland needs **Accessibility** permission to overlay on the notch. macOS will prompt on first launch — approve it in System Settings → Privacy & Security → Accessibility.

---

## 5. Chrome Extension

The extension adds a sidebar to any browser tab. Use it to clip content, run agents, and browse your research digest without leaving the page.

### Build

```bash
cd apps/chrome-extension
npm install
npm run build        # produces dist/
# For live reload during development:
npm run dev
```

### Load in Chrome

1. Open `chrome://extensions`
2. Enable **Developer mode** (top right toggle)
3. Click **Load unpacked** → select `apps/chrome-extension/dist/`
4. The Flow icon appears in your toolbar

### Configure

Click the extension icon → open **Settings** tab:

- **API URL** — set to `http://localhost:18000` (or your deployed URL)
- **Token** — paste a JWT from the web app (Settings → API token) or log in directly in the extension

### Features

| Tab | What it does |
| --- | ------------ |
| **Digest** | Today's research papers, scored and filterable |
| **Clip** | Send current page content to your Flow knowledge base |
| **Run** | Chat with an agent in a sidebar panel |
| **Settings** | API URL + auth token configuration |

---

## 6. Agent tools configuration

In the web app, go to **Agents** → pick an agent → **Config** → **Knowledge & Tools** tab.

| Toggle | Effect |
| ------ | ------ |
| **Retrieve** | Enable Qdrant hybrid RAG (requires Qdrant running + papers embedded) |
| **Long-term memory** | Cross-session memory via `AsyncPostgresStore` |
| **Sandbox** | Python code execution inside agent responses |
| **Tavily search** | Live web search via Tavily API |
| **Fetch webpage** | Agent can fetch and read URLs |
| **arXiv search** | Direct arXiv paper search tool |
| **HuggingFace papers** | HuggingFace daily paper feed as a tool |

---

## 7. Common issues

**Export to Obsidian returns 400**
→ Check `FLOW_OBSIDIAN_VAULT_PATH` in `.env` and that the volume is mounted in `docker-compose.yml`.

**Embed as Knowledge shows `embedded: 0`**
→ Confirm `FLOW_QDRANT_URL` is set and the Qdrant container is running. Check `docker compose logs api` for `upsert_failed`.

**Graph query returns no results**
→ The graph needs nodes. Go to `/graph` → click **Sync** to index your agents, skills, and papers into the knowledge graph.

**FlowIsland not appearing**
→ Ensure you're running on a MacBook with a physical notch. The app uses `CGDisplayIsBuiltin` to detect the built-in display — it won't appear on external monitors.

**Chrome extension auth fails**
→ The token expires. Re-copy it from the web app (Settings → API token) and paste it into the extension Settings tab.
