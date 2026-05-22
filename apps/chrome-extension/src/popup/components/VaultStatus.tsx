import { useEffect, useState } from "react";
import { listMCPServers, pingMCPServer, type MCPServer } from "../../lib/mcp-client";

interface Props {
  workspaceId: string;
}

type ServerStatus = { server: MCPServer; ok: boolean | null };

export function VaultStatus({ workspaceId }: Props) {
  const [statuses, setStatuses] = useState<ServerStatus[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
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
        // no servers or network error — stay empty
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [workspaceId]);

  if (loading) return <p style={{ fontSize: 11, color: "#888" }}>Checking MCP servers…</p>;
  if (statuses.length === 0) return null;

  return (
    <div style={{ marginTop: 8 }}>
      <p style={{ fontSize: 11, fontWeight: 600, marginBottom: 4, color: "#555" }}>MCP / Vault</p>
      {statuses.map(({ server, ok }) => (
        <div
          key={server.id}
          style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, marginBottom: 3 }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: ok === null ? "#ccc" : ok ? "#22c55e" : "#ef4444",
              flexShrink: 0,
            }}
          />
          <span style={{ color: "#333", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {server.name}
          </span>
          <span style={{ color: "#999", marginLeft: "auto" }}>
            {ok === null ? "…" : ok ? "online" : "offline"}
          </span>
        </div>
      ))}
    </div>
  );
}
