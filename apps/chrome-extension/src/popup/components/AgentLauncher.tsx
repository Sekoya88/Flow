import { useEffect, useState } from "react";
import { listAgents, runAgent, Agent } from "../../lib/flow-api";

export function AgentLauncher({ workspaceId }: { workspaceId: string }) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [selectedId, setSelectedId] = useState("");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<"idle" | "running" | "ok" | "error">("idle");

  useEffect(() => {
    listAgents(workspaceId)
      .then((a) => {
        setAgents(a);
        if (a[0]) setSelectedId(a[0].id);
      })
      .catch(() => null)
      .finally(() => setLoaded(true));
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

  if (!loaded) return <div className="tab-pane"><p style={{ fontSize: 11, color: "var(--f-500)" }}>Loading agents…</p></div>;

  if (agents.length === 0) {
    return (
      <div className="tab-pane">
        <div className="agent-empty">
          <span className="agent-empty-icon">⚡</span>
          <p className="agent-empty-text">
            No agents in this workspace.<br />
            Create one in Flow to get started.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="tab-pane">
      <div>
        <label className="label">Agent</label>
        <div className="select-wrap">
          <select
            className="field"
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
          >
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>
      </div>
      <div>
        <label className="label">Message</label>
        <textarea
          className="field"
          rows={4}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => e.metaKey && e.key === "Enter" && launch()}
          placeholder="Message for the agent…"
        />
      </div>
      <button
        className="btn btn-primary btn-full"
        onClick={launch}
        disabled={status === "running" || !message.trim()}
      >
        {status === "running" ? "Launching…" : "Run Agent"}
      </button>
      {status === "ok" && <p className="msg-ok">✓ Execution queued</p>}
      {status === "error" && <div className="msg-error">Launch failed — check connection.</div>}
    </div>
  );
}
