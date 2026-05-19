"use client";

import { useRef, useState } from "react";
import { Brain, Upload, Link2, RefreshCw, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ToolCallLog, type ToolCall } from "@/components/flow/ToolCallLog";
import { PathViz } from "./PathViz";
import { apiFetch, getApiBase } from "@/lib/api";
import { cn } from "@/lib/utils";
import { getToken } from "@/lib/auth";

interface Message {
  role: "user" | "agent";
  text: string;
  toolCalls?: ToolCall[];
  path?: { nodes: string[]; edges: string[] };
}

interface Props {
  workspaceId: string;
  onHighlight?: (nodeIds: string[]) => void;
  onPathHighlight?: (labels: string[]) => void;
}

export function GraphQueryPanel({ workspaceId, onHighlight, onPathHighlight }: Props) {
  const [tab, setTab] = useState<"query" | "import">("query");
  const [messages, setMessages] = useState<Message[]>([
    { role: "agent", text: "Graph loaded. Ask me anything about your notes." },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const [obsidianUrl, setObsidianUrl] = useState("http://localhost:27123");
  const [obsidianKey, setObsidianKey] = useState("");
  const [obsidianPath, setObsidianPath] = useState("/");
  const [syncPath, setSyncPath] = useState("");
  const [importing, setImporting] = useState(false);
  const [importStatus, setImportStatus] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);

  async function sendQuery() {
    if (!input.trim() || loading) return;
    const question = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setLoading(true);

    const toolCalls: ToolCall[] = [];
    let path: { nodes: string[]; edges: string[] } | undefined;
    let answer = "";

    try {
      const token = getToken();
      const res = await fetch(`${getApiBase()}/api/v1/kg/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ workspace_id: workspaceId, question, stream: true }),
      });

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        let event = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) { event = line.slice(7).trim(); continue; }
          if (line.startsWith("data: ")) {
            const data = JSON.parse(line.slice(6));
            if (event === "kg_tool_call") {
              toolCalls.push({ id: `tc-${toolCalls.length}`, tool: data.tool, input: data.args ?? {}, output: "", duration_ms: 0, status: "success" });
            } else if (event === "kg_path") {
              path = { nodes: data.nodes, edges: data.edges };
              onPathHighlight?.(data.nodes);
            } else if (event === "kg_highlight") {
              onHighlight?.(data.node_ids);
            } else if (event === "kg_answer") {
              answer = data.text;
            }
          }
        }
      }
    } catch {
      answer = "Error querying graph.";
    }

    setMessages((prev) => [...prev, { role: "agent", text: answer, toolCalls, path }]);
    setLoading(false);
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setImporting(true);
    setImportStatus(null);
    const form = new FormData();
    Array.from(files).forEach((f) => form.append("files", f));
    try {
      const res = await apiFetch<{ ingested: number; total: number }>(
        `/api/v1/kg/ingest/upload?workspace_id=${workspaceId}`,
        { method: "POST", body: form },
      );
      setImportStatus(`✓ ${res.ingested} notes ingested (${res.total} total)`);
    } catch {
      setImportStatus("Upload failed.");
    } finally {
      setImporting(false);
    }
  }

  async function handleObsidianConnect() {
    setImporting(true);
    setImportStatus(null);
    try {
      const data = await apiFetch<{ ingested: number; total: number }>("/api/v1/kg/ingest/obsidian", {
        method: "POST",
        json: { workspace_id: workspaceId, base_url: obsidianUrl, api_key: obsidianKey, vault_path: obsidianPath },
      });
      setImportStatus(`✓ ${data.ingested} notes ingested from Obsidian`);
    } catch {
      setImportStatus("Connection failed. Check URL and API key.");
    } finally {
      setImporting(false);
    }
  }

  async function handleSync() {
    if (!syncPath) return;
    setImporting(true);
    setImportStatus(null);
    try {
      const data = await apiFetch<{ ingested: number; total: number }>("/api/v1/kg/sync", {
        method: "POST",
        json: { workspace_id: workspaceId, vault_path: syncPath },
      });
      setImportStatus(`✓ ${data.ingested} notes synced`);
    } catch {
      setImportStatus("Sync failed.");
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="flex h-full flex-col border-l border-flow-800 bg-card/95" style={{ width: 360 }}>
      <div className="flex items-center gap-2 border-b border-flow-800 px-4 py-3">
        <Brain className="h-3.5 w-3.5 text-flow-violet" aria-hidden />
        <span className="flex-1 text-xs font-semibold text-foreground/80">Graph Query</span>
        <div className="flex gap-1">
          {(["query", "import"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "rounded px-2.5 py-1 text-[11px] font-medium transition-colors",
                tab === t ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t === "query" ? "Query" : "Import"}
            </button>
          ))}
        </div>
      </div>

      {tab === "query" && (
        <>
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {messages.map((m, i) => (
              <div key={i} className={cn("flex flex-col gap-1.5", m.role === "user" && "items-end")}>
                <div
                  className={cn(
                    "max-w-[90%] rounded-lg px-3 py-2 text-[12px] leading-relaxed",
                    m.role === "user"
                      ? "rounded-br-sm bg-flow-violet/10 border border-flow-violet/20 text-foreground"
                      : "rounded-bl-sm bg-muted/50 border border-flow-800 text-foreground",
                  )}
                >
                  {m.text}
                </div>
                {m.toolCalls && m.toolCalls.length > 0 && (
                  <ToolCallLog calls={m.toolCalls} className="w-full" />
                )}
                {m.path && m.path.nodes.length > 0 && (
                  <div className="w-full rounded-md border border-emerald-500/20 bg-emerald-500/5 p-2">
                    <PathViz nodes={m.path.nodes} edges={m.path.edges} />
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                <span className="animate-pulse">●</span> Querying graph…
              </div>
            )}
            <div ref={bottomRef} />
          </div>
          <div className="border-t border-flow-800 p-3">
            <div className="flex gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendQuery()}
                placeholder="Ask about your notes…"
                className="h-8 text-[12px]"
              />
              <Button size="icon" className="h-8 w-8 shrink-0" onClick={sendQuery} disabled={loading}>
                <Send className="h-3.5 w-3.5" />
              </Button>
            </div>
            <div className="mt-2 flex flex-wrap gap-1">
              {["How does X relate to Y?", "What do I know about…", "Summarize my notes on…"].map((hint) => (
                <button
                  key={hint}
                  onClick={() => setInput(hint)}
                  className="rounded-full border border-flow-800 bg-muted/20 px-2 py-0.5 text-[9px] text-muted-foreground hover:border-border hover:text-foreground transition-colors"
                >
                  {hint}
                </button>
              ))}
            </div>
          </div>
        </>
      )}

      {tab === "import" && (
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {importStatus && (
            <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-[11px] text-emerald-400">
              {importStatus}
            </div>
          )}

          <div className="rounded-xl border border-flow-800 bg-muted/30 p-4 space-y-2.5">
            <p className="text-[11px] font-semibold text-foreground/80 flex items-center gap-1.5">
              <Upload className="h-3.5 w-3.5 text-flow-violet" /> Upload .md files
            </p>
            <p className="text-[10px] text-muted-foreground">Wikilinks, tags, and frontmatter YAML are parsed.</p>
            <label className="block cursor-pointer rounded-lg border border-dashed border-flow-800 p-4 text-center text-[11px] text-muted-foreground hover:border-flow-violet/50 hover:bg-flow-violet/5 transition-colors">
              <input type="file" multiple accept=".md" className="hidden" onChange={(e) => handleUpload(e.target.files)} />
              Drop .md files or click to select
            </label>
          </div>

          <div className="rounded-xl border border-flow-800 bg-muted/30 p-4 space-y-2.5">
            <p className="text-[11px] font-semibold text-foreground/80 flex items-center gap-1.5">
              <Link2 className="h-3.5 w-3.5 text-flow-violet" /> Obsidian Local REST API
            </p>
            <p className="text-[10px] text-muted-foreground">Install the &quot;Local REST API&quot; plugin in Obsidian.</p>
            <Input value={obsidianUrl} onChange={(e) => setObsidianUrl(e.target.value)} placeholder="http://localhost:27123" className="h-7 text-[11px] font-mono" />
            <Input value={obsidianKey} onChange={(e) => setObsidianKey(e.target.value)} placeholder="API key" type="password" className="h-7 text-[11px] font-mono" />
            <Input value={obsidianPath} onChange={(e) => setObsidianPath(e.target.value)} placeholder="Vault path (e.g. /AI Research)" className="h-7 text-[11px]" />
            <Button size="sm" className="w-full h-7 text-[11px]" onClick={handleObsidianConnect} disabled={importing}>
              {importing ? "Connecting…" : "Connect & Import"}
            </Button>
          </div>

          <div className="rounded-xl border border-flow-800 bg-muted/30 p-4 space-y-2.5">
            <p className="text-[11px] font-semibold text-foreground/80 flex items-center gap-1.5">
              <RefreshCw className="h-3.5 w-3.5 text-flow-violet" /> Filesystem Sync
            </p>
            <Input value={syncPath} onChange={(e) => setSyncPath(e.target.value)} placeholder="/Users/you/Obsidian/Brain" className="h-7 text-[11px] font-mono" />
            <Button size="sm" variant="outline" className="w-full h-7 text-[11px]" onClick={handleSync} disabled={importing || !syncPath}>
              {importing ? "Syncing…" : "Sync Now"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
