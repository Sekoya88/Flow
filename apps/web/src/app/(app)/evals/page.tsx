"use client";

import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Database,
  Pencil,
  Play,
  Plus,
  Terminal,
  Trash2,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { apiFetch, getApiBase } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────

type GoldenSet = {
  id: string;
  name: string;
  description: string;
  item_count: number;
  created_at: string;
};

type GoldenItem = {
  id: string;
  input_text: string;
  expected_output: string;
  scoring_criteria: string;
  created_at: string;
};

type AgentRow = { id: string; name: string };

type EvalLog = {
  id: string;
  kind: "info" | "success" | "warning" | "error" | "done";
  message?: string;
  results?: any;
  timestamp: string;
};

// ── Page ─────────────────────────────────────────────────────────────

export default function EvalsPage() {
  const workspaceId = useStore((s) => s.workspaces[0]?.id ?? null);

  const [sets, setSets] = useState<GoldenSet[]>([]);
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [expandedSetId, setExpandedSetId] = useState<string | null>(null);
  const [setItems, setSetItems] = useState<Record<string, GoldenItem[]>>({});
  const [loadingSets, setLoadingSets] = useState(false);

  const [selectedSetId, setSelectedSetId] = useState<string | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

  const [logs, setLogs] = useState<EvalLog[]>([]);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<any | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Create set form
  const [showCreateSet, setShowCreateSet] = useState(false);
  const [newSetName, setNewSetName] = useState("");
  const [newSetDesc, setNewSetDesc] = useState("");
  const [creatingSet, setCreatingSet] = useState(false);

  // Add item form
  const [addingItemToSet, setAddingItemToSet] = useState<string | null>(null);
  const [newItem, setNewItem] = useState({ input_text: "", expected_output: "", scoring_criteria: "" });
  const [addingItem, setAddingItem] = useState(false);

  useEffect(() => {
    if (!workspaceId) return;
    setLoadingSets(true);
    Promise.all([
      apiFetch<{ sets: GoldenSet[] }>("/api/v1/golden-sets"),
      apiFetch<{ agents: AgentRow[] }>(`/api/v1/agents?workspace_id=${workspaceId}`),
    ])
      .then(([sData, aData]) => {
        setSets(sData.sets ?? []);
        setAgents(aData.agents ?? []);
        if (sData.sets?.[0]) setSelectedSetId(sData.sets[0].id);
        if (aData.agents?.[0]) setSelectedAgentId(aData.agents[0].id);
      })
      .catch(console.warn)
      .finally(() => setLoadingSets(false));
  }, [workspaceId]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  async function expandSet(setId: string) {
    if (expandedSetId === setId) {
      setExpandedSetId(null);
      return;
    }
    setExpandedSetId(setId);
    if (setItems[setId]) return;
    try {
      const data = await apiFetch<{ items: GoldenItem[] }>(`/api/v1/golden-sets/${setId}`);
      setSetItems((prev) => ({ ...prev, [setId]: data.items ?? [] }));
    } catch (e) {
      console.warn("load items failed", e);
    }
  }

  async function createSet() {
    if (!newSetName.trim()) return;
    setCreatingSet(true);
    try {
      const result = await apiFetch<{ id: string; name: string }>("/api/v1/golden-sets", {
        method: "POST",
        body: JSON.stringify({ name: newSetName.trim(), description: newSetDesc.trim() }),
      });
      const newSet: GoldenSet = {
        id: result.id,
        name: result.name,
        description: newSetDesc.trim(),
        item_count: 0,
        created_at: new Date().toISOString(),
      };
      setSets((prev) => [newSet, ...prev]);
      if (!selectedSetId) setSelectedSetId(result.id);
      setNewSetName("");
      setNewSetDesc("");
      setShowCreateSet(false);
    } catch (e) {
      console.warn("create set failed", e);
    } finally {
      setCreatingSet(false);
    }
  }

  async function addItem(setId: string) {
    if (!newItem.input_text.trim() || !newItem.expected_output.trim()) return;
    setAddingItem(true);
    try {
      const result = await apiFetch<{ id: string }>(`/api/v1/golden-sets/${setId}/items`, {
        method: "POST",
        body: JSON.stringify(newItem),
      });
      const item: GoldenItem = {
        id: result.id,
        ...newItem,
        created_at: new Date().toISOString(),
      };
      setSetItems((prev) => ({ ...prev, [setId]: [...(prev[setId] ?? []), item] }));
      setSets((prev) => prev.map((s) => s.id === setId ? { ...s, item_count: s.item_count + 1 } : s));
      setNewItem({ input_text: "", expected_output: "", scoring_criteria: "" });
      setAddingItemToSet(null);
    } catch (e) {
      console.warn("add item failed", e);
    } finally {
      setAddingItem(false);
    }
  }

  async function deleteItem(setId: string, itemId: string) {
    try {
      await apiFetch(`/api/v1/golden-sets/${setId}/items/${itemId}`, { method: "DELETE" });
      setSetItems((prev) => ({ ...prev, [setId]: (prev[setId] ?? []).filter((i) => i.id !== itemId) }));
      setSets((prev) => prev.map((s) => s.id === setId ? { ...s, item_count: Math.max(0, s.item_count - 1) } : s));
    } catch (e) {
      console.warn("delete item failed", e);
    }
  }

  async function runEvaluation() {
    if (!selectedSetId || !selectedAgentId) return;
    setLogs([]);
    setResults(null);
    setRunning(true);
    try {
      const params = new URLSearchParams({ set_id: selectedSetId, agent_id: selectedAgentId });
      const resp = await fetch(`${getApiBase()}/api/v1/evaluations/run?${params}`, {
        method: "GET",
        headers: { Accept: "text/event-stream", Authorization: `Bearer ${getToken()}` },
      });
      const reader = resp.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No reader");
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        for (const line of chunk.split("\n").filter((l) => l.startsWith("data: "))) {
          try {
            const data = JSON.parse(line.slice(6));
            setLogs((prev) => [...prev, {
              id: Math.random().toString(),
              kind: data.kind,
              message: data.message,
              results: data.results,
              timestamp: new Date().toLocaleTimeString(),
            }]);
            if (data.kind === "done") {
              setResults(data.results);
              setRunning(false);
            }
          } catch (e) {
            console.error("SSE parse error", e, line);
          }
        }
      }
    } catch (err: any) {
      setLogs((prev) => [...prev, { id: "err", kind: "error", message: err.message, timestamp: new Date().toLocaleTimeString() }]);
      setRunning(false);
    }
  }

  const selectedSet = sets.find((s) => s.id === selectedSetId);
  const selectedAgent = agents.find((a) => a.id === selectedAgentId);

  return (
    <div className="flex h-full flex-col">
      <FlowPageHeader title="Evaluations" />
      <div className="flex flex-1 overflow-hidden gap-0">

        {/* ── Left: Dataset Browser ─────────────────── */}
        <div className="w-80 shrink-0 border-r border-border/50 flex flex-col overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border/40">
            <div className="flex items-center gap-2">
              <Database className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-sm font-medium">Golden Sets</span>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => setShowCreateSet((v) => !v)}
              title="New set"
            >
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>

          {showCreateSet && (
            <div className="px-3 py-3 border-b border-border/40 bg-muted/20 space-y-2">
              <Input
                placeholder="Set name"
                value={newSetName}
                onChange={(e) => setNewSetName(e.target.value)}
                className="h-7 text-xs"
              />
              <Input
                placeholder="Description (optional)"
                value={newSetDesc}
                onChange={(e) => setNewSetDesc(e.target.value)}
                className="h-7 text-xs"
              />
              <div className="flex gap-1">
                <Button size="sm" className="h-6 text-[11px] px-2 gap-1" onClick={createSet} disabled={creatingSet || !newSetName.trim()}>
                  <Plus className="h-2.5 w-2.5" />
                  {creatingSet ? "Creating…" : "Create"}
                </Button>
                <Button size="sm" variant="ghost" className="h-6 text-[11px] px-2" onClick={() => setShowCreateSet(false)}>Cancel</Button>
              </div>
            </div>
          )}

          <div className="flex-1 overflow-y-auto">
            {loadingSets ? (
              <div className="flex items-center justify-center py-8 gap-2 text-xs text-muted-foreground">
                <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-flow-brand border-t-transparent" />
                Loading…
              </div>
            ) : sets.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-10 text-center px-4">
                <Database className="h-6 w-6 text-muted-foreground/30" />
                <p className="text-xs text-muted-foreground">No golden sets yet.</p>
              </div>
            ) : (
              sets.map((s) => {
                const expanded = expandedSetId === s.id;
                const items = setItems[s.id] ?? [];
                const isSelected = selectedSetId === s.id;
                return (
                  <div key={s.id} className={cn("border-b border-border/30 last:border-0", isSelected && "bg-flow-brand/5")}>
                    <div
                      className="flex items-center gap-2 px-3 py-2.5 cursor-pointer hover:bg-muted/30 transition-colors select-none"
                      onClick={() => { setSelectedSetId(s.id); void expandSet(s.id); }}
                    >
                      {expanded ? (
                        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium truncate">{s.name}</p>
                        {s.description && (
                          <p className="text-[10px] text-muted-foreground truncate">{s.description}</p>
                        )}
                      </div>
                      <Badge variant="outline" className="text-[10px] font-mono h-4 px-1.5 shrink-0">
                        {s.item_count}
                      </Badge>
                    </div>

                    {expanded && (
                      <div className="bg-muted/10 px-3 pb-2 space-y-1.5">
                        {items.length === 0 ? (
                          <p className="text-[10px] text-muted-foreground py-1 pl-1">No items yet.</p>
                        ) : (
                          items.map((item) => (
                            <div
                              key={item.id}
                              className="group flex items-start gap-2 rounded-lg border border-border/30 bg-card/60 p-2"
                            >
                              <div className="flex-1 min-w-0 space-y-0.5">
                                <p className="text-[11px] font-medium text-foreground/90 line-clamp-2">{item.input_text}</p>
                                <p className="text-[10px] text-muted-foreground line-clamp-1">→ {item.expected_output}</p>
                                {item.scoring_criteria && (
                                  <p className="text-[10px] text-muted-foreground/60 italic line-clamp-1">{item.scoring_criteria}</p>
                                )}
                              </div>
                              <button
                                onClick={() => void deleteItem(s.id, item.id)}
                                className="opacity-0 group-hover:opacity-100 shrink-0 rounded p-0.5 text-muted-foreground hover:text-destructive transition-all"
                              >
                                <Trash2 className="h-3 w-3" />
                              </button>
                            </div>
                          ))
                        )}

                        {addingItemToSet === s.id ? (
                          <div className="space-y-1.5 pt-1 border-t border-border/30">
                            <Textarea
                              placeholder="Input text"
                              value={newItem.input_text}
                              onChange={(e) => setNewItem((n) => ({ ...n, input_text: e.target.value }))}
                              rows={2}
                              className="text-[11px] resize-none"
                            />
                            <Textarea
                              placeholder="Expected output"
                              value={newItem.expected_output}
                              onChange={(e) => setNewItem((n) => ({ ...n, expected_output: e.target.value }))}
                              rows={2}
                              className="text-[11px] resize-none"
                            />
                            <Input
                              placeholder="Scoring criteria (optional)"
                              value={newItem.scoring_criteria}
                              onChange={(e) => setNewItem((n) => ({ ...n, scoring_criteria: e.target.value }))}
                              className="h-6 text-[11px]"
                            />
                            <div className="flex gap-1">
                              <Button
                                size="sm"
                                className="h-6 text-[10px] px-2 gap-1"
                                onClick={() => void addItem(s.id)}
                                disabled={addingItem || !newItem.input_text.trim() || !newItem.expected_output.trim()}
                              >
                                {addingItem ? "Adding…" : "Add"}
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 text-[10px] px-2"
                                onClick={() => setAddingItemToSet(null)}
                              >
                                Cancel
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <button
                            onClick={() => { setAddingItemToSet(s.id); setNewItem({ input_text: "", expected_output: "", scoring_criteria: "" }); }}
                            className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground py-1 transition-colors"
                          >
                            <Plus className="h-2.5 w-2.5" />
                            Add item
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ── Right: Run Panel ──────────────────────── */}
        <div className="flex-1 flex flex-col overflow-hidden p-6 gap-5">

          {/* Run config bar */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2 min-w-0">
              <Label className="text-xs shrink-0 text-muted-foreground">Dataset</Label>
              <select
                value={selectedSetId ?? ""}
                onChange={(e) => setSelectedSetId(e.target.value || null)}
                className="h-8 rounded-lg border border-border/50 bg-card text-xs px-2 pr-6 min-w-[140px] text-foreground"
              >
                {sets.map((s) => (
                  <option key={s.id} value={s.id}>{s.name} ({s.item_count})</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2 min-w-0">
              <Label className="text-xs shrink-0 text-muted-foreground">Agent</Label>
              <select
                value={selectedAgentId ?? ""}
                onChange={(e) => setSelectedAgentId(e.target.value || null)}
                className="h-8 rounded-lg border border-border/50 bg-card text-xs px-2 pr-6 min-w-[140px] text-foreground"
              >
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            </div>
            <Button
              onClick={() => void runEvaluation()}
              disabled={running || !selectedSetId || !selectedAgentId}
              size="sm"
              className="gap-2 h-8 shadow-sm shadow-flow-brand/20"
            >
              <Play className="h-3.5 w-3.5" />
              {running ? "Evaluating…" : "Run evaluation"}
            </Button>
          </div>

          <div className="flex flex-1 gap-5 overflow-hidden">
            {/* Live logs */}
            <div className="flex-1 flex flex-col min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Live logs</span>
              </div>
              <div className="flex-1 bg-[#080808] rounded-xl border border-border/30 p-4 overflow-y-auto font-mono text-xs min-h-0">
                {logs.length === 0 ? (
                  <div className="text-muted-foreground/40 h-full flex items-center justify-center italic text-[11px]">
                    Select a dataset and agent, then click Run evaluation.
                  </div>
                ) : (
                  <div className="flex flex-col gap-1.5">
                    {logs.map((log) => (
                      <div key={log.id} className="flex items-start gap-3">
                        <span className="text-muted-foreground/40 w-16 shrink-0 text-[10px] pt-px">{log.timestamp}</span>
                        <span
                          className={cn(
                            "text-[11px] leading-relaxed",
                            log.kind === "error" && "text-red-400",
                            log.kind === "warning" && "text-amber-400",
                            log.kind === "success" && "text-emerald-400",
                            log.kind === "done" && "text-sky-400",
                            log.kind === "info" && "text-zinc-300",
                          )}
                        >
                          {log.kind === "error" && "✗ "}
                          {log.kind === "warning" && "⚠ "}
                          {log.kind === "success" && "✓ "}
                          {log.kind === "done" && "● "}
                          {log.message || (log.kind === "done" && "Stream closed.")}
                        </span>
                      </div>
                    ))}
                    <div ref={logsEndRef} />
                  </div>
                )}
              </div>
            </div>

            {/* Summary + status */}
            <div className="w-56 shrink-0 flex flex-col gap-4">
              <div className="rounded-xl border border-border/50 bg-card/60 p-4 space-y-4">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Summary</p>
                {results ? (
                  <>
                    <Metric label="Pass rate" value={`${(results.pass_rate * 100).toFixed(0)}%`} highlight={results.pass_rate >= 0.7} />
                    <Metric label="Avg score" value={results.avg_score.toFixed(3)} />
                    <Metric label="Items scored" value={`${results.scored_items ?? "—"} / ${results.total_items ?? "—"}`} />
                  </>
                ) : (
                  <p className="text-xs text-muted-foreground/50 italic">Awaiting run…</p>
                )}
              </div>

              {results && (
                <div className={cn(
                  "rounded-xl border p-3 flex items-start gap-2.5",
                  results.pass_rate < 0.7
                    ? "bg-red-500/8 border-red-500/30 text-red-400"
                    : "bg-emerald-500/8 border-emerald-500/30 text-emerald-400",
                )}>
                  {results.pass_rate < 0.7 ? (
                    <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                  )}
                  <div>
                    <p className="text-xs font-medium">
                      {results.pass_rate < 0.7 ? "Regression detected" : "Agent stable"}
                    </p>
                    <p className="text-[11px] opacity-70 mt-0.5">
                      {results.pass_rate < 0.7 ? "Proposal generated for review." : "Meets production criteria."}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Detailed breakdown */}
          {results?.results && (
            <div className="space-y-2 overflow-y-auto max-h-72">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Item breakdown</p>
              {results.results.map((r: any, i: number) => (
                <div key={i} className="flex gap-3 rounded-xl border border-border/40 bg-card/60 p-3">
                  <div className={cn(
                    "shrink-0 w-12 flex flex-col items-center justify-center rounded-lg py-2",
                    r.score >= 0.7 ? "bg-emerald-500/10" : "bg-red-500/10",
                  )}>
                    <span className={cn("text-base font-bold tabular-nums", r.score >= 0.7 ? "text-emerald-400" : "text-red-400")}>
                      {(r.score * 100).toFixed(0)}
                    </span>
                    <span className="text-[9px] text-muted-foreground">/ 100</span>
                  </div>
                  <div className="flex-1 min-w-0 space-y-1">
                    <p className="text-xs font-medium text-foreground/90 line-clamp-1">"{r.input_text}"</p>
                    <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">{r.rationale}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-0.5">{label}</p>
      <p className={cn("text-2xl font-light tabular-nums", highlight === false && "text-red-400", highlight === true && "text-emerald-400")}>
        {value}
      </p>
    </div>
  );
}
