import { useCallback, useEffect, useState } from "react";
import { listMCPServers, pingMCPServer, type MCPServer } from "../../lib/mcp-client";

type ServerStatus = { server: MCPServer; ok: boolean | null };

export function VaultStatus({ workspaceId }: { workspaceId: string }) {
  const [statuses, setStatuses] = useState<ServerStatus[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setStatuses([]);

    async function run() {
      try {
        const servers = await listMCPServers(workspaceId);
        const initial: ServerStatus[] = servers.map((s) => ({ server: s, ok: null }));
        if (!cancelled) setStatuses(initial);
        await Promise.all(
          servers.map(async (s, i) => {
            try {
              const result = await pingMCPServer(s.id);
              if (!cancelled) {
                setStatuses((prev) =>
                  prev.map((item, idx) => (idx === i ? { ...item, ok: result.ok } : item))
                );
              }
            } catch {
              if (!cancelled) {
                setStatuses((prev) =>
                  prev.map((item, idx) => (idx === i ? { ...item, ok: false } : item))
                );
              }
            }
          })
        );
      } catch {
        // no servers or network error
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    run();
    return () => { cancelled = true; };
  }, [workspaceId]);

  useEffect(() => {
    return load();
  }, [load]);

  return (
    <div className="tab-pane">
      <div className="mcp-header">
        <label className="label" style={{ marginBottom: 0 }}>MCP Servers</label>
        <button className="btn btn-ghost btn-sm" onClick={load} disabled={loading}>
          {loading ? "…" : "Refresh"}
        </button>
      </div>

      {loading && statuses.length === 0 ? (
        <p className="mcp-empty">Checking servers…</p>
      ) : statuses.length === 0 ? (
        <p className="mcp-empty">
          No MCP servers configured.<br />
          Add one in Flow → Settings → MCP.
        </p>
      ) : (
        statuses.map(({ server, ok }) => (
          <div key={server.id} className="mcp-row">
            <span className={`dot ${ok === null ? "dot-pending" : ok ? "dot-ok" : "dot-error"}`} />
            <div className="mcp-info">
              <p className="mcp-name">{server.name}</p>
              <p className="mcp-url">{server.url}</p>
            </div>
            <span className="mcp-status">
              {ok === null ? "checking" : ok ? "online" : "offline"}
            </span>
          </div>
        ))
      )}
    </div>
  );
}
