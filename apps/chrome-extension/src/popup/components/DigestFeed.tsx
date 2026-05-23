import { useEffect, useRef, useState } from "react";
import { deletePaper, listPapers, patchPaper, runDigest, Paper } from "../../lib/flow-api";
import { getToken, getApiUrl } from "../../lib/auth";

type StatusTab = "unread" | "read" | "all";

type LogEntry = { id: string; label: string; detail: string; cls: string };

const EVENT_CONFIG: Record<string, { label: string; cls: string }> = {
  "digest.start":          { label: "Digest started",   cls: "log-entry-run"  },
  "digest.fetch_done":     { label: "Papers fetched",   cls: "log-entry-info" },
  "digest.scoring":        { label: "Scoring",          cls: "log-entry-info" },
  "digest.filter_done":    { label: "Filtered",         cls: "log-entry-info" },
  "digest.summarize_done": { label: "Summarized",       cls: "log-entry-info" },
  "digest.persist_done":   { label: "Saved to DB",      cls: "log-entry-info" },
  "digest.complete":       { label: "Complete",         cls: "log-entry-ok"   },
};

function detailFromPayload(kind: string, payload: Record<string, unknown>): string {
  if (kind === "digest.fetch_done")     return `${payload.count} papers`;
  if (kind === "digest.scoring")        return `${payload.count} papers`;
  if (kind === "digest.filter_done")    return `${payload.kept}/${payload.total} relevant`;
  if (kind === "digest.summarize_done") return `${payload.count} papers`;
  if (kind === "digest.persist_done")   return `${payload.persisted} papers`;
  if (kind === "digest.complete")       return `${payload.persisted} saved`;
  return "";
}

export function DigestFeed({ workspaceId }: { workspaceId: string }) {
  const [tab, setTab] = useState<StatusTab>("unread");
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [digestRunning, setDigestRunning] = useState(false);
  const logBottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  function reload() {
    setLoading(true);
    listPapers(workspaceId, tab === "all" ? undefined : tab)
      .then(setPapers)
      .catch(() => setPapers([]))
      .finally(() => setLoading(false));
  }

  useEffect(() => { reload(); }, [workspaceId, tab]);

  useEffect(() => {
    logBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Cleanup SSE on unmount
  useEffect(() => () => { abortRef.current?.abort(); }, []);

  async function startDigest() {
    if (running) return;
    setRunning(true);
    setLogs([]);
    try {
      await runDigest(workspaceId);
      setDigestRunning(true);
      subscribeSSE();
    } catch {
      setRunning(false);
    }
  }

  async function subscribeSSE() {
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    const [token, apiBase] = await Promise.all([getToken(), getApiUrl()]);
    try {
      const res = await fetch(`${apiBase}/api/v1/stream?workspace_id=${workspaceId}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) return;
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          try {
            const parsed = JSON.parse(line.slice(5).trim()) as Record<string, unknown>;
            const kind = (parsed.kind as string) ?? "unknown";
            const cfg = EVENT_CONFIG[kind];
            if (cfg) {
              const entry: LogEntry = {
                id: `${Date.now()}-${Math.random()}`,
                label: cfg.label,
                detail: detailFromPayload(kind, parsed),
                cls: cfg.cls,
              };
              setLogs((prev) => [...prev, entry]);
            }
            if (kind === "digest.complete") {
              setDigestRunning(false);
              setRunning(false);
              ctrl.abort();
              setTimeout(() => { setLogs([]); reload(); }, 2500);
            }
          } catch { /* malformed line */ }
        }
      }
    } catch (e) {
      if ((e as Error)?.name !== "AbortError") {
        setDigestRunning(false);
        setRunning(false);
      }
    }
  }

  async function handleMarkRead(id: string) {
    await patchPaper(id, "read").catch(() => null);
    setPapers((prev) => prev.map((p) => p.id === id ? { ...p, status: "read" } : p));
    if (tab === "unread") setPapers((prev) => prev.filter((p) => p.id !== id));
  }

  async function handleDelete(id: string) {
    await deletePaper(id).catch(() => null);
    setPapers((prev) => prev.filter((p) => p.id !== id));
  }

  function scoreClass(s: number) {
    return s >= 0.8 ? "score-hi" : s >= 0.6 ? "score-mid" : "score-lo";
  }

  return (
    <div className="tab-pane">
      {/* Toolbar */}
      <div className="digest-toolbar">
        <label className="label" style={{ marginBottom: 0 }}>Research Digest</label>
        <button
          className={`btn btn-sm ${running ? "btn-ghost" : "btn-violet"}`}
          onClick={startDigest}
          disabled={running}
        >
          {running ? "Running…" : "Run Digest"}
        </button>
      </div>

      {/* SSE log panel */}
      {(digestRunning || logs.length > 0) && (
        <div className="log-panel">
          {logs.length === 0 && (
            <div className="log-entry"><span className="log-entry-ts">—</span> Connecting…</div>
          )}
          {logs.map((e) => (
            <div key={e.id} className="log-entry">
              <span className={`log-entry-label ${e.cls}`}>{e.label}</span>
              {e.detail && <span>{e.detail}</span>}
            </div>
          ))}
          <div ref={logBottomRef} />
        </div>
      )}

      {/* Status tabs */}
      <div className="status-tabs">
        {(["unread", "read", "all"] as StatusTab[]).map((t) => (
          <button
            key={t}
            className={`status-tab ${tab === t ? "status-tab-active" : ""}`}
            onClick={() => setTab(t)}
          >
            {t === "all" ? "All" : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Paper list */}
      {loading ? (
        <p style={{ fontSize: 11, color: "var(--f-500)", textAlign: "center", padding: "20px 0" }}>
          Loading…
        </p>
      ) : papers.length === 0 ? (
        <p style={{ fontSize: 11, color: "var(--f-500)", textAlign: "center", padding: "20px 0", lineHeight: 1.6 }}>
          No {tab !== "all" ? tab : ""} papers.<br />Run a digest to populate.
        </p>
      ) : (
        <div className="paper-list">
          {papers.map((p) => (
            <div key={p.id} className="paper-card">
              <p className="paper-title">{p.title}</p>
              {p.tldr && <p className="paper-tldr">{p.tldr}</p>}
              <div className="paper-footer">
                <span className={`paper-score ${scoreClass(p.relevance_score)}`}>
                  {(p.relevance_score * 100).toFixed(0)}% match
                </span>
                {p.source_url && (
                  <a href={p.source_url} target="_blank" rel="noopener noreferrer" className="paper-link">
                    Open →
                  </a>
                )}
              </div>
              <div className="paper-actions">
                {p.status !== "read" && (
                  <button className="paper-action paper-action-read" onClick={() => handleMarkRead(p.id)}>
                    Mark read
                  </button>
                )}
                <button className="paper-action paper-action-del" onClick={() => handleDelete(p.id)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
