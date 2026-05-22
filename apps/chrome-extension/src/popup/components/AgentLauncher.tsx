import { useEffect, useState } from "react";
import { listAgents, runAgent, Agent } from "../../lib/flow-api";

const s = {
  section: { padding: "16px", borderBottom: "1px solid #1e1e3f" },
  label: { fontSize: "10px", color: "#6b7280", display: "block" as const, marginBottom: "6px", letterSpacing: "0.05em", textTransform: "uppercase" as const },
  select: { width: "100%", background: "#1a1a2e", border: "1px solid #3d3d7f", borderRadius: "6px", padding: "6px 10px", color: "#e2e2ff", fontSize: "11px", outline: "none" },
  textarea: { width: "100%", background: "#1a1a2e", border: "1px solid #3d3d7f", borderRadius: "6px", padding: "8px 10px", color: "#e2e2ff", fontSize: "11px", resize: "vertical" as const, minHeight: "56px", outline: "none", marginTop: "8px" },
  btn: { marginTop: "8px", background: "#4f46e5", color: "#fff", border: "none", borderRadius: "6px", padding: "6px 12px", cursor: "pointer", fontSize: "10px", fontWeight: "600" },
  success: { marginTop: "6px", fontSize: "10px", color: "#34d399" },
  error: { marginTop: "6px", fontSize: "10px", color: "#f87171" },
};

export function AgentLauncher({ workspaceId }: { workspaceId: string }) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<"idle" | "running" | "ok" | "error">("idle");

  useEffect(() => {
    listAgents(workspaceId)
      .then((a) => {
        setAgents(a);
        if (a[0]) setSelectedId(a[0].id);
      })
      .catch(() => null);
  }, [workspaceId]);

  async function launch() {
    if (!selectedId || !message.trim()) return;
    setStatus("running");
    try {
      await runAgent(workspaceId, selectedId, message);
      setStatus("ok");
      setMessage("");
      setTimeout(() => setStatus("idle"), 2500);
    } catch {
      setStatus("error");
      setTimeout(() => setStatus("idle"), 3000);
    }
  }

  if (agents.length === 0) return null;

  return (
    <div style={s.section}>
      <label style={s.label}>Run Agent</label>
      <select style={s.select} value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
        {agents.map((a) => (
          <option key={a.id} value={a.id}>
            {a.name}
          </option>
        ))}
      </select>
      <textarea
        style={s.textarea}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="Message for the agent…"
      />
      <button style={s.btn} onClick={launch} disabled={status === "running" || !message.trim()}>
        {status === "running" ? "Launching…" : "Run"}
      </button>
      {status === "ok" && <p style={s.success}>Execution queued!</p>}
      {status === "error" && <p style={s.error}>Failed. Check connection.</p>}
    </div>
  );
}
