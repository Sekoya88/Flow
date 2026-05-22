import { useEffect, useState } from "react";
import { ingestKnowledge } from "../../lib/flow-api";

const s = {
  section: { padding: "16px", borderBottom: "1px solid #1e1e3f" },
  label: { fontSize: "10px", color: "#6b7280", display: "block" as const, marginBottom: "6px", letterSpacing: "0.05em", textTransform: "uppercase" as const },
  textarea: { width: "100%", background: "#1a1a2e", border: "1px solid #3d3d7f", borderRadius: "6px", padding: "8px 10px", color: "#e2e2ff", fontSize: "11px", resize: "vertical" as const, minHeight: "72px", outline: "none" },
  btn: { marginTop: "8px", background: "#4f46e5", color: "#fff", border: "none", borderRadius: "6px", padding: "6px 12px", cursor: "pointer", fontSize: "10px", fontWeight: "600" },
  success: { marginTop: "6px", fontSize: "10px", color: "#34d399" },
  error: { marginTop: "6px", fontSize: "10px", color: "#f87171" },
};

export function QuickCapture({ workspaceId }: { workspaceId: string }) {
  const [text, setText] = useState("");
  const [status, setStatus] = useState<"idle" | "saving" | "ok" | "error">("idle");
  const [pageUrl, setPageUrl] = useState<string | undefined>();
  const [pageTitle, setPageTitle] = useState("Web capture");

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
      await ingestKnowledge(workspaceId, pageTitle, text, pageUrl);
      setStatus("ok");
      setText("");
      setTimeout(() => setStatus("idle"), 2000);
    } catch {
      setStatus("error");
      setTimeout(() => setStatus("idle"), 3000);
    }
  }

  return (
    <div style={s.section}>
      <label style={s.label}>Quick Capture</label>
      <textarea
        style={s.textarea}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste or type text to save to Flow knowledge base…"
      />
      <button style={s.btn} onClick={save} disabled={status === "saving" || !text.trim()}>
        {status === "saving" ? "Saving…" : "Save to Flow"}
      </button>
      {status === "ok" && <p style={s.success}>Saved!</p>}
      {status === "error" && <p style={s.error}>Failed. Check connection.</p>}
    </div>
  );
}
