# Flow — Roadmap

## Shipped: Second Brain (May 2026)

The core second brain use case is complete end-to-end.

| Feature | Status |
| ------- | ------ |
| PDF / .docx / .md / .txt upload (up to 20 MB) | ✅ |
| URL crawl — extract and index any web page | ✅ |
| pgvector retrieval, k=8, numbered citations | ✅ |
| Inline `[1]` `[2]` citation markers in answers | ✅ |
| Sources panel — click to expand exact chunk | ✅ |
| Onboarding wizard (use-case selection → first doc upload) | ✅ |
| 👎 feedback → agent negatives → improves future retrievals | ✅ |

---

## Next: Coding Assistant (Milestone 2)

Give agents the ability to write, run, and iterate on code in a sandboxed environment.

| Feature | Notes |
| ------- | ----- |
| Persistent sandbox per workspace | Each workspace gets an isolated Python environment |
| File I/O inside sandbox | Read/write files produced by code runs |
| Code execution results streamed via SSE | Same `token` event pattern as current answers |
| Agent template: `code-runner` | Pre-configured with sandbox tool enabled |
| Result display in Run page | Rendered output + stdout/stderr toggle |

---

## Next: Personal Automation (Milestone 3)

Schedule recurring agent tasks that run against your knowledge base without manual input.

| Feature | Notes |
| ------- | ----- |
| Cron-style task scheduler | Define a prompt + schedule (daily, weekly, on upload) |
| Execution history per task | Review past runs, outputs, citations |
| Email / webhook delivery | Send answer to an email or POST to a URL |
| Agent template: `scheduled-digest` | Pre-configured for recurring summaries |

---

## Deferred (revisit after Milestone 3)

- Per-workspace LLM config (BYOK — bring your own OpenAI/Anthropic key)
- Custom agent templates via UI (no-code graph topology editor)
- RAG audit UI (chunk-level retrieval trace already stored, UI deferred)
- Execution replay
- Collaborative workspaces / multi-user RBAC beyond current owner model
- Kubernetes / production deployment hardening
- RAG evaluation dashboard (precision/recall over time)
