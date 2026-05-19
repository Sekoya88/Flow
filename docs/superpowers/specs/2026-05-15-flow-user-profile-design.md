# Flow — User Profile & Preference System

**Date:** 2026-05-15
**Status:** Approved
**Branch:** to be created
**Roadmap:** Subsystem A

---

## Problem

Flow agents have no persistent knowledge of who the user is. Every run starts cold: the user's preferred language, communication style, domain context, and hard prohibitions must be re-stated or re-discovered each time. Facts extracted by `FlowMemoryMiddleware` capture *what happened*, not *who the user is*.

Inspired by OpenHuman's `PROFILE.md` + personalization cache (6 typed facet classes, scored with decay, editable by user), this feature makes Flow agents continuously smarter about the user across all runs.

---

## Scope

One subsystem (Roadmap A). Does not cover:
- Subsystem B (byte-stable system prompts)
- Hierarchical memory compression (Subsystem E)
- Team/workspace-level shared preferences (future)

---

## Architecture

### Overview

```
Onboarding (first login or empty profile):
  /onboarding/profile          → guided questionnaire (5–7 questions)
    → answers inserted as active preferences immediately

CV upload (any time):
  POST /api/v1/preferences/import-cv  (PDF or DOCX)
    → extract_preferences_from_cv(llm, text)
    → inserted as active preferences (user-provided = trusted)

After every agent run:
  FlowMemoryMiddleware.after_agent
    → extract_preferences(llm, conversation)   # LLM extraction
    → upsert into user_preferences table        # reinforcement or new candidate
    → auto-graduate if thresholds met

Before every agent run:
  FlowMemoryMiddleware.before_agent
    → load_effective_profile(pool, workspace_id, user_id, agent_id)
    → inject as SystemMessage([User Preferences] block)

User:
  /settings/profile            → manage global preferences + upload CV
  /agents/{id}/config#prefs    → manage per-agent overrides
```

### Profile scoping

Global base + per-agent override. For each `class`, agent-specific rows shadow global rows. `veto` facets from both layers are always unioned (never shadowed).

---

## Data Model

### Migration `0014_user_preferences.py`

```sql
CREATE TABLE user_preferences (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id         UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id              UUID NOT NULL,
  agent_id             UUID REFERENCES agents(id) ON DELETE CASCADE,  -- NULL = global
  class                TEXT NOT NULL CHECK (class IN
                           ('style','tooling','veto','goal','domain','channel')),
  value                TEXT NOT NULL,
  score                FLOAT NOT NULL DEFAULT 0.5,
  status               TEXT NOT NULL DEFAULT 'candidate'
                           CHECK (status IN ('candidate','provisional','active')),
  pinned               BOOLEAN NOT NULL DEFAULT FALSE,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_reinforced_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  decay_half_life_days INT NOT NULL DEFAULT 30,
  -- agent_id NULL = global; PostgreSQL treats NULL != NULL in UNIQUE,
  -- so use a coalesced surrogate to enforce uniqueness for global rows too.
  UNIQUE (workspace_id, user_id, COALESCE(agent_id, '00000000-0000-0000-0000-000000000000'::uuid), class, value)
);

CREATE INDEX idx_user_preferences_lookup
  ON user_preferences (workspace_id, user_id, agent_id, status);
```

### Facet classes

| Class | Examples |
|-------|---------|
| `style` | "concise answers", "always cite sources", "use bullet points" |
| `tooling` | "uses Python", "prefers PostgreSQL over MySQL" |
| `veto` | "never use eval()", "never suggest jQuery" |
| `goal` | "building a SaaS product", "learning ML" |
| `domain` | "works in fintech", "regulatory compliance environment" |
| `channel` | "always use markdown", "code blocks for all snippets" |

### Effective score (decay)

Computed at read time — no background job:

```python
import math
effective_score = row.score * (0.5 ** (days_since_reinforced / row.decay_half_life_days))
```

Rows with `effective_score < 0.1` are skipped and deleted during profile load. Pinned rows (`pinned=TRUE`) skip decay entirely.

---

## Extraction Pipeline

### Trigger

`FlowMemoryMiddleware.after_agent` — runs after every execution, alongside fact extraction. Uses a small model (`gpt-4o-mini` or `claude-haiku-4-5`).

### Extraction prompt

```
Given this conversation, extract signals about the user's stable preferences.
Return JSON array: [{"class": "<class>", "value": "<short declarative phrase>"}]
Classes: style, tooling, veto, goal, domain, channel
Rules:
- Only extract clear, stable signals (not one-off requests)
- value must be a short declarative phrase (max 10 words)
- Omit anything ambiguous or run-specific
- Return [] if no clear preferences found
```

### Upsert (reinforcement deduplication)

```sql
INSERT INTO user_preferences
  (workspace_id, user_id, agent_id, class, value)
VALUES ($1, $2, NULL, $3, $4)
ON CONFLICT (workspace_id, user_id, agent_id, class, value)
DO UPDATE SET
  score = LEAST(1.0, user_preferences.score + 0.1),
  last_reinforced_at = NOW()
RETURNING *
```

### Auto-graduation thresholds

Checked after every upsert:

| Transition | Condition |
|-----------|-----------|
| `candidate` → `provisional` | effective score ≥ 0.7 (= 2 reinforcements from default 0.5 baseline) |
| `provisional` → `active` | effective score ≥ 0.9 (= 4 reinforcements from 0.7) |
| Any → pruned | effective score < 0.1 (lazy, on load) |

Each extraction event adds +0.1 to `score` (capped at 1.0). Decay is applied at read time so score in DB is always the raw reinforced value; `effective_score` is the decayed projection.

---

## Injection

### Load query

```sql
SELECT class, value, score, status, pinned, last_reinforced_at, decay_half_life_days
FROM user_preferences
WHERE workspace_id = $1
  AND user_id = $2
  AND (agent_id = $3 OR agent_id IS NULL)
  AND status IN ('provisional', 'active')
ORDER BY agent_id NULLS LAST, score DESC
```

Candidates are never injected. Decayed rows (effective < 0.1) are deleted on load.

### Merge logic

For each `class`: agent-specific rows win over global rows (take top 3 agent-specific; fall back to top 3 global if none). Exception: `veto` facets are unioned from both layers.

### Injected block

Prepended as a `SystemMessage` to `state["messages"]` before the planner:

```
[User Preferences]
Style: concise answers; always cite sources (learning)
Tooling: Python; PostgreSQL
Goal: building a SaaS product
Veto: never use eval(); never suggest jQuery
Domain: fintech environment
```

`provisional` entries are marked `(learning)`. Max 3 entries per class, total cap ~300 tokens. This block is not trimmed by `FlowCostMiddleware`.

---

## Onboarding Questionnaire

Shown as a modal on first login (or when `user_preferences` is empty for the user). 5–7 targeted questions, one per screen. Answers are inserted directly as `active` preferences (user-declared = fully trusted, no graduation needed).

### Questions

| # | Question | Target class |
|---|---------|-------------|
| 1 | "What programming languages do you use most?" | `tooling` |
| 2 | "What's your main professional domain?" (e.g. fintech, healthcare, SaaS) | `domain` |
| 3 | "How do you prefer answers formatted?" (concise / detailed / bullet points / narrative) | `style` |
| 4 | "What are you currently working on or trying to learn?" | `goal` |
| 5 | "Are there tools, patterns, or suggestions you never want to see?" | `veto` |
| 6 | "Any tech stack preferences we should know about?" (frameworks, DBs, cloud) | `tooling` |
| 7 | "How should code examples be presented?" (always / only when asked / never) | `channel` |

Questions 5–7 are optional (user can skip). The questionnaire can be re-triggered from `/settings/profile` ("Re-run setup").

### Flow

```
GET /api/v1/preferences/onboarding-status
→ { completed: bool, preference_count: int }

POST /api/v1/preferences/onboarding
Body: { answers: [{ class, value }] }
→ { created: int }   # number of preferences inserted
```

Answers are bulk-inserted as `active` preferences. Existing preferences are not overwritten (idempotent upsert — if value already exists, just reinforce it).

---

## CV / Résumé Import

User uploads a PDF or DOCX résumé. The backend parses the text, runs LLM extraction against it, and bulk-inserts the results as `active` preferences. This provides a rich cold-start signal before any agent runs.

### Endpoint

```
POST /api/v1/preferences/import-cv
Content-Type: multipart/form-data
Body: file (PDF or DOCX, max 5MB), workspace_id

Response: { extracted: int, preview: [{ class, value }] }
```

### Processing pipeline

1. Parse file to plain text:
   - PDF: `pypdf` (already in ecosystem or add as dep)
   - DOCX: `python-docx`
2. Truncate to 8 000 chars (résumés are dense; cap avoids token blowout)
3. Run LLM extraction with an extended prompt:

```
You are reading a professional résumé. Extract stable user preferences for an AI assistant.
Return JSON: [{"class": "<class>", "value": "<short declarative phrase>"}]
Classes: style, tooling, veto, goal, domain, channel
Focus on:
- Programming languages and frameworks mentioned → tooling
- Industry / domain / sector → domain
- Seniority and communication preferences implied by role titles → style
- Career goals or current focus areas → goal
Return 10–25 items. Short declarative phrases only (max 10 words each).
```

4. All extracted items inserted as `active` preferences (user uploaded = trusted).
5. `preview` array returned to frontend for immediate display.

### Frontend (in `/settings/profile`)

- Drag-and-drop zone: "Drop your résumé here (PDF or DOCX)" with a "Browse" fallback
- After upload: "We found N preferences from your résumé" toast + preview list
- User can immediately delete/veto any extracted item from the preview before it's confirmed — but default is all accepted

### Dependencies added

| Package | Reason |
|---------|--------|
| `pypdf>=4.0` | PDF text extraction |
| `python-docx>=1.1` | DOCX text extraction |

---

## API Endpoints

All endpoints scoped to `workspace_id` + `user_id` from JWT. No body-supplied identity fields accepted.

### `GET /api/v1/preferences`

```
Query: workspace_id, agent_id? (optional), status? (optional), class? (optional)
Response: { global: PreferenceOut[], agent_specific: PreferenceOut[] }
```

### `POST /api/v1/preferences`

```
Body: { workspace_id, agent_id?, class, value, status="active" }
Response: PreferenceOut
```

Manually created preferences start as `active` immediately (user-declared = trusted).

### `PATCH /api/v1/preferences/{id}`

```
Body: { action: "promote" | "pin" | "unpin" | "forget" | "veto" }
Response: PreferenceOut | { deleted: true }
```

Actions:
- `promote` → advance one stage
- `pin` → `status=active`, `pinned=true`
- `unpin` → `pinned=false`
- `forget` → hard delete
- `veto` → delete this row + insert `veto`-class entry to suppress future extraction of same value

### `DELETE /api/v1/preferences/{id}`

```
Response: 204
```

### Schema

```python
class PreferenceOut(BaseModel):
    id: UUID
    class_: str = Field(alias="class")
    value: str
    score: float           # effective decayed score, computed at read time
    status: str
    pinned: bool
    agent_id: UUID | None
    last_reinforced_at: datetime
    created_at: datetime
```

---

## Frontend

### `/settings/profile` — global profile

- Sections grouped by class; each collapsible
- Row: value text + score bar + status badge (`candidate` gray / `provisional` amber / `active` green / `pinned` indigo)
- Row actions: **Promote**, **Pin** (⚑), **Forget** (✕), **Veto** (🚫)
- "Add manually" inline input per section
- Banner at top: **"N preferences pending review"** → scrolls to candidate section

### Candidate review queue — tab within `/settings/profile`

- Lists `candidate` preferences with source run attribution: `"extracted from: Research Assistant — 2026-05-14"`
- Bulk: "Promote all" / "Dismiss all"
- Individual: Promote / Forget

### Agent config page — `Preferences` tab

- Global preferences shown read-only (grayed, labeled "Global")
- Agent-specific overrides below with full row actions
- "Add override for this agent" → inline input with class dropdown

---

## Backend File Structure

```
services/api/flow/
  infrastructure/
    persistence/
      repo.py                      # MODIFY: load_profile, upsert_preference, patch_preference
  application/
    preference_service.py          # NEW: extract_preferences, effective_score, auto_graduate,
                                   #      extract_from_cv, process_onboarding_answers
  interfaces/
    http/
      routes/
        preferences.py             # NEW: 6 endpoints (CRUD + import-cv + onboarding)
  infrastructure/
    llm/
      middleware/
        memory.py                  # MODIFY: inject profile in before_agent, extract in after_agent
```

Migration:
```
services/api/migrations/versions/0014_user_preferences.py
```

Dependencies added to `pyproject.toml`:
```
pypdf>=4.0,<6         # PDF text extraction (CV import)
python-docx>=1.1,<2   # DOCX text extraction (CV import)
```

---

## Frontend File Structure

```
apps/web/src/
  app/(app)/settings/profile/
    page.tsx                       # NEW: global profile page + CV dropzone
  app/(app)/onboarding/profile/
    page.tsx                       # NEW: onboarding questionnaire (shown on first login)
  app/(app)/agents/[id]/config/
    page.tsx                       # MODIFY: add Preferences tab
  components/preferences/
    PreferenceRow.tsx               # NEW: value + score + badge + row actions
    PreferenceSection.tsx           # NEW: class group (collapsible)
    CandidateQueue.tsx              # NEW: pending review queue
    AddPreferenceInline.tsx         # NEW: inline add input with class selector
    CVDropzone.tsx                  # NEW: drag-and-drop CV upload + preview list
    OnboardingQuestionnaire.tsx     # NEW: step-by-step question flow (5–7 steps)
  lib/
    usePreferences.ts               # NEW: data hook → GET /api/v1/preferences
    useOnboardingStatus.ts          # NEW: GET /api/v1/preferences/onboarding-status
```

---

## Testing

| File | What it verifies |
|------|-----------------|
| `tests/test_preference_service.py` | extraction returns correct classes; upsert deduplicates; auto-graduation at correct score thresholds; decay formula correct; veto inserts veto row; CV extraction truncates at 8 000 chars; onboarding answers bulk-insert as active |
| `tests/test_preference_routes.py` | GET scopes to workspace+user only; PATCH promote advances status; PATCH veto inserts veto row and deletes original; DELETE 204; import-cv rejects files > 5 MB; onboarding-status returns correct completed flag |
| `tests/test_middleware_memory.py` (extend) | before_agent injects profile block when active preferences exist; candidates not injected; provisional marked (learning); veto always included regardless of agent override |
| `apps/web/__tests__/PreferenceSection.test.tsx` | row actions call correct API; promote advances badge; pin shows indigo badge; candidate queue bulk actions work |
| `apps/web/__tests__/CVDropzone.test.tsx` | rejects non-PDF/DOCX files; shows preview after upload; all items accepted by default |
| `apps/web/__tests__/OnboardingQuestionnaire.test.tsx` | advances through steps; skippable questions work; submit calls onboarding endpoint with correct payload |

---

## Success Criteria

1. Fresh user: onboarding questionnaire shown on first login; answers immediately visible in profile page as active preferences
2. CV upload: dropping a PDF résumé inserts 10–25 preferences as active within 5s; preview shown before confirmation
3. After 2 runs where the user consistently asks for Python code, `tooling: uses Python` auto-graduates from `candidate` to `provisional` (score reaches 0.7)
4. Active/provisional preferences appear in `[User Preferences]` block in every subsequent run
5. `veto` preferences suppress future extraction of the same value
6. Agent-level override shadows global preference for the same class
7. Pinned preferences survive 90+ days without decay
8. All test files pass; no regressions in existing middleware tests
