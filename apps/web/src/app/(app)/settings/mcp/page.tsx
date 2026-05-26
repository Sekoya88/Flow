"use client";

import { useEffect, useState } from "react";
import {
  Check,
  ChevronRight,
  Loader2,
  Plug,
  Plus,
  RefreshCw,
  Server,
  Trash2,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { apiFetch } from "@/lib/api";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";

type MCPServer = {
  id: string;
  workspace_id: string;
  name: string;
  url: string;
  transport: string;
  active: boolean;
  tool_count: number;
  metadata: Record<string, unknown>;
  created_at: string;
};

type ToolAssignment = {
  id: string;
  tool_name: string;
  description: string | null;
  enabled: boolean;
};

function AddMCPServerModal({
  wsId,
  onCreated,
}: {
  wsId: string;
  onCreated: (s: MCPServer) => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [transport, setTransport] = useState("sse");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    if (!wsId) return;
    setSaving(true);
    setError(null);
    try {
      const server = await apiFetch<MCPServer>("/api/v1/mcp/servers", {
        method: "POST",
        json: { workspace_id: wsId, name, url, transport },
      });
      onCreated(server);
      setOpen(false);
      setName("");
      setUrl("");
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" className="gap-1.5 font-mono text-xs">
          <Plus className="h-3.5 w-3.5" />
          Add Server
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="font-mono text-sm">Add MCP Server</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label className="font-mono text-xs">Name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Flow MCP"
              className="font-mono text-xs"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="font-mono text-xs">SSE URL</Label>
            <Input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="http://localhost:18001/sse"
              className="font-mono text-xs"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="font-mono text-xs">Transport</Label>
            <Input
              value={transport}
              onChange={(e) => setTransport(e.target.value)}
              placeholder="sse"
              className="font-mono text-xs"
            />
          </div>
          {error && (
            <p className="rounded-[6px] bg-destructive/10 px-3 py-2 font-mono text-[11px] text-destructive">
              {error}
            </p>
          )}
          <Button
            onClick={create}
            disabled={saving || !name || !url}
            className="w-full font-mono text-xs"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Create"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ToolsDrawer({
  server,
  onClose,
  onSynced,
}: {
  server: MCPServer | null;
  onClose: () => void;
  onSynced: (serverId: string, count: number) => void;
}) {
  const [tools, setTools] = useState<ToolAssignment[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    if (!server) return;
    setLoading(true);
    apiFetch<ToolAssignment[]>(`/api/v1/mcp/servers/${server.id}/tools`)
      .then(setTools)
      .catch(() => setTools([]))
      .finally(() => setLoading(false));
  }, [server?.id]);

  async function handleSync() {
    if (!server) return;
    setSyncing(true);
    try {
      const res = await apiFetch<{ ok: boolean; tool_count: number; tools: ToolAssignment[] }>(
        `/api/v1/mcp/servers/${server.id}/tools/sync`,
        { method: "POST" },
      );
      if (res.ok) {
        setTools(res.tools);
        onSynced(server.id, res.tool_count);
      }
    } catch {
      // error shown implicitly — syncing state reverts
    } finally {
      setSyncing(false);
    }
  }

  return (
    <Sheet open={server !== null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent
        side="right"
        className="flex w-[min(100vw-1rem,28rem)] flex-col gap-0"
      >
        <SheetHeader className="border-b border-flow-800 pb-4 text-left">
          <div className="flex items-center justify-between">
            <SheetTitle className="font-mono text-sm">
              Tools — {server?.name}
            </SheetTitle>
            <button
              onClick={handleSync}
              disabled={syncing}
              className="inline-flex h-7 items-center gap-1 rounded-[6px] border border-flow-700 px-2 font-mono text-[10px] text-flow-400 hover:bg-flow-800 hover:text-flow-200 transition-colors disabled:opacity-50"
            >
              {syncing ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <RefreshCw className="h-3 w-3" />
              )}
              Sync
            </button>
          </div>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-4 w-4 animate-spin text-flow-500" />
            </div>
          ) : tools.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-10 text-center">
              <p className="font-mono text-xs text-flow-500">
                No tools discovered yet.
              </p>
              <button
                onClick={handleSync}
                disabled={syncing}
                className="inline-flex h-7 items-center gap-1.5 rounded-[6px] border border-flow-700 px-3 font-mono text-[10px] text-flow-400 hover:bg-flow-800 hover:text-flow-200 transition-colors disabled:opacity-50"
              >
                {syncing ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
                Sync from server
              </button>
            </div>
          ) : (
            <ul className="space-y-1.5">
              {tools.map((t) => (
                <li
                  key={t.id ?? t.tool_name}
                  className="rounded-[6px] border border-flow-800 bg-flow-900/50 px-3 py-2.5 space-y-0.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-medium">{t.tool_name}</span>
                    <Badge
                      variant={t.enabled ? "secondary" : "outline"}
                      className="font-mono text-[9px] shrink-0"
                    >
                      {t.enabled ? "enabled" : "disabled"}
                    </Badge>
                  </div>
                  {t.description && (
                    <p className="text-[11px] text-flow-500 leading-relaxed line-clamp-2">
                      {t.description}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function MCPServerCard({
  server,
  onDelete,
  onToggleTools,
}: {
  server: MCPServer;
  onDelete: (id: string) => void;
  onToggleTools: (s: MCPServer) => void;
}) {
  const toolCount = server.tool_count ?? 0;
  const [pingStatus, setPingStatus] = useState<"idle" | "ok" | "error">("idle");
  const [pinging, setPinging] = useState(false);

  async function ping() {
    setPinging(true);
    try {
      const healthUrl = server.url.replace(/\/sse$/, "").replace(/\/$/, "") + "/health";
      const r = await fetch(healthUrl, { signal: AbortSignal.timeout(5000) });
      setPingStatus(r.ok ? "ok" : "error");
    } catch {
      setPingStatus("error");
    } finally {
      setPinging(false);
      setTimeout(() => setPingStatus("idle"), 4000);
    }
  }

  return (
    <div className="flex items-center justify-between gap-4 rounded-[8px] border border-flow-800 bg-flow-900/50 px-4 py-3">
      <div className="flex min-w-0 items-center gap-3">
        <div
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-[6px] border",
            server.active
              ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-400"
              : "border-flow-700 bg-flow-800 text-flow-500",
          )}
        >
          <Server className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="truncate font-mono text-xs font-semibold">{server.name}</p>
            {toolCount > 0 && (
              <Badge variant="outline" className="font-mono text-[9px] shrink-0 border-flow-700">
                {toolCount} tools
              </Badge>
            )}
          </div>
          <p className="truncate font-mono text-[10px] text-flow-500">{server.url}</p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        {pingStatus === "ok" && <Check className="h-3.5 w-3.5 text-emerald-400" />}
        {pingStatus === "error" && <X className="h-3.5 w-3.5 text-destructive" />}
        <button
          onClick={ping}
          disabled={pinging}
          className="inline-flex h-7 items-center gap-1 rounded-[6px] border border-flow-700 px-2 font-mono text-[10px] text-flow-400 hover:bg-flow-800 hover:text-flow-200 transition-colors disabled:opacity-50"
        >
          {pinging ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Wifi className="h-3 w-3" />
          )}
          Ping
        </button>
        <button
          onClick={() => onToggleTools(server)}
          className="inline-flex h-7 items-center gap-1 rounded-[6px] border border-flow-700 px-2 font-mono text-[10px] text-flow-400 hover:bg-flow-800 hover:text-flow-200 transition-colors"
        >
          <Plug className="h-3 w-3" />
          Tools
          <ChevronRight className="h-3 w-3" />
        </button>
        <button
          onClick={() => onDelete(server.id)}
          className="inline-flex h-7 w-7 items-center justify-center rounded-[6px] border border-flow-700 text-flow-600 hover:bg-destructive/10 hover:text-destructive transition-colors"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

export default function MCPSettingsPage() {
  const wsId = useStore((s) => s.workspaces[0]?.id ?? "");
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(false);
  const [toolsServer, setToolsServer] = useState<MCPServer | null>(null);

  function handleSynced(serverId: string, count: number) {
    setServers((prev) =>
      prev.map((s) => (s.id === serverId ? { ...s, tool_count: count } : s)),
    );
  }

  useEffect(() => {
    if (!wsId) return;
    setLoading(true);
    apiFetch<MCPServer[]>(`/api/v1/mcp/servers?workspace_id=${wsId}`)
      .then(setServers)
      .catch(() => setServers([]))
      .finally(() => setLoading(false));
  }, [wsId]);

  async function handleDelete(id: string) {
    await apiFetch(`/api/v1/mcp/servers/${id}`, { method: "DELETE" });
    setServers((prev) => prev.filter((s) => s.id !== id));
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-mono text-sm font-semibold uppercase tracking-widest text-flow-50">
            MCP Servers
          </h2>
          <p className="mt-0.5 text-xs text-flow-500">
            Connect Model Context Protocol servers to extend agent capabilities.
          </p>
        </div>
        <AddMCPServerModal wsId={wsId} onCreated={(s) => setServers((p) => [s, ...p])} />
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-4 w-4 animate-spin text-flow-500" />
        </div>
      ) : servers.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-[10px] border border-dashed border-flow-800 py-14 text-center">
          <WifiOff className="h-7 w-7 text-flow-700" />
          <p className="font-mono text-xs text-flow-500">No MCP servers yet. Add one above.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {servers.map((server) => (
            <MCPServerCard
              key={server.id}
              server={server}
              onDelete={handleDelete}
              onToggleTools={setToolsServer}
            />
          ))}
        </div>
      )}

      <ToolsDrawer server={toolsServer} onClose={() => setToolsServer(null)} onSynced={handleSynced} />
    </div>
  );
}
