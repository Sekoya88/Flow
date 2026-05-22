import { useEffect, useState } from "react";
import { ingestKnowledge } from "../../lib/flow-api";

export function QuickCapture({ workspaceId }: { workspaceId: string }) {
  const [text, setText] = useState("");
  const [status, setStatus] = useState<"idle" | "saving" | "ok" | "error">("idle");
  const [pageUrl, setPageUrl] = useState<string | undefined>();
  const [pageTitle, setPageTitle] = useState("");

  useEffect(() => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        setPageUrl(tabs[0].url);
        setPageTitle(tabs[0].title ?? "Web capture");
      }
    });
  }, []);

  async function save() {
    if (!text.trim()) return;
    setStatus("saving");
    try {
      await ingestKnowledge(workspaceId, pageTitle || "Web capture", text, pageUrl);
      setStatus("ok");
      setText("");
      setTimeout(() => setStatus("idle"), 2000);
    } catch {
      setStatus("error");
      setTimeout(() => setStatus("idle"), 3000);
    }
  }

  return (
    <div className="tab-pane">
      {pageTitle && (
        <div className="page-badge">
          <span className="page-badge-dot" />
          <span className="page-badge-title">{pageTitle}</span>
        </div>
      )}
      <div>
        <label className="label">Note</label>
        <textarea
          className="field"
          rows={5}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.metaKey && e.key === "Enter" && save()}
          placeholder="Paste or type text to save to Flow knowledge base…"
        />
      </div>
      <div className="capture-actions">
        <span className="capture-hint">⌘↵ to save</span>
        <button
          className="btn btn-primary"
          onClick={save}
          disabled={status === "saving" || !text.trim()}
        >
          {status === "saving" ? "Saving…" : "Save to Flow"}
        </button>
      </div>
      {status === "ok" && <p className="msg-ok">✓ Saved to knowledge base</p>}
      {status === "error" && <div className="msg-error">Save failed — check connection.</div>}
    </div>
  );
}
