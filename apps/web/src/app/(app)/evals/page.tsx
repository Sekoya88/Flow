"use client";

import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Database,
  Download,
  Play,
  Plus,
  Sparkles,
  Terminal,
  Trash2,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { apiFetch, getApiBase } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { logger } from "@/lib/logger";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────

type GoldenSet = { id: string; name: string; description: string; item_count: number; created_at: string };
type GoldenItem = { id: string; input_text: string; expected_output: string; scoring_criteria: string };
type AgentRow = { id: string; name: string; template: string; config: Record<string, unknown> };
type EvalLog = { id: string; kind: "info" | "success" | "warning" | "error" | "done" | "item_result" | "progress" | "summary"; message?: string; results?: unknown; score?: number; timestamp: string };
type HistoryPoint = { run_id: string; run_at: string; version_label: string; avg_score: number; pass_rate: number; total: number };

// ── Sparkline ────────────────────────────────────────────────────────

function Sparkline({ data, uid }: { data: number[]; uid: string }) {
  if (data.length < 2) return <span className="text-[10px] text-muted-foreground/40 italic">no history</span>;
  const W = 80; const H = 24; const pad = 2;
  const w = W - pad * 2; const h = H - pad * 2;
  const min = Math.min(...data); const max = Math.max(...data);
  const range = max - min || 0.01;
  const pts = data.map((v, i) => `${(pad + (i / (data.length - 1)) * w).toFixed(1)},${(pad + (1 - (v - min) / range) * h).toFixed(1)}`).join(" ");
  const color = data[data.length - 1] >= 0.7 ? "#10b981" : "#ef4444";
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="shrink-0">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ── Agent template metadata ──────────────────────────────────────────

const TPL: Record<string, { color: string; label: string }> = {
  "deer_flow":               { color: "text-teal-400 bg-teal-500/10 border-teal-500/20", label: "Deer Flow" },
  "tool-agent":              { color: "text-amber-400 bg-amber-500/10 border-amber-500/20", label: "Tool Agent" },
  "linear-3":                { color: "text-sky-400 bg-sky-500/10 border-sky-500/20", label: "Linear" },
  "researcher-critic-writer":{ color: "text-violet-400 bg-violet-500/10 border-violet-500/20", label: "Research" },
  "orchestrator":            { color: "text-blue-400 bg-blue-500/10 border-blue-500/20", label: "Orchestrator" },
};

// ── Page ─────────────────────────────────────────────────────────────

export default function EvalsPage() {
  const workspaceId = useStore((s) => s.workspaces[0]?.id ?? null);

  const [sets, setSets] = useState<GoldenSet[]>([]);
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [loadingSets, setLoadingSets] = useState(false);
  const [seeding, setSeeding] = useState(false);

  const [selectedSetId, setSelectedSetId] = useState<string | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

  const [expandedSetId, setExpandedSetId] = useState<string | null>(null);
  const [setItems, setSetItems] = useState<Record<string, GoldenItem[]>>({});
  const [loadingItems, setLoadingItems] = useState(false);

  const [showCreateSet, setShowCreateSet] = useState(false);
  const [newSetName, setNewSetName] = useState("");
  const [newSetDesc, setNewSetDesc] = useState("");
  const [creatingSet, setCreatingSet] = useState(false);
  const [addingItem, setAddingItem] = useState(false);
  const [newItem, setNewItem] = useState({ input_text: "", expected_output: "", scoring_criteria: "" });
  const [addingItemToSet, setAddingItemToSet] = useState<string | null>(null);

  const [logs, setLogs] = useState<EvalLog[]>([]);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<any>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const [history, setHistory] = useState<HistoryPoint[]>([]);

  // ── Auto-improve & Regression state ──
  const [improving, setImproving] = useState(false);
  const [improveResult, setImproveResult] = useState<any>(null);
  const [showRegression, setShowRegression] = useState(false);
  const [regressionData, setRegressionData] = useState<any>(null);
  const [loadingRegression, setLoadingRegression] = useState(false);

  // ── Load data ────────────────────────────────────────────────────────

  useEffect(() => {
    if (!workspaceId) return;
    setLoadingSets(true);
    Promise.all([
      apiFetch<{ sets: GoldenSet[] }>("/api/v1/golden-sets"),
      apiFetch<{ agents: AgentRow[] }>(`/api/v1/workspaces/${workspaceId}/agents`),
    ])
      .then(([sData, aData]) => {
        const s = sData.sets ?? [];
        const a = aData.agents ?? [];
        setSets(s);
        setAgents(a);
        if (s[0]) { setSelectedSetId(s[0].id); setExpandedSetId(s[0].id); }
        if (a[0]) setSelectedAgentId(a[0].id);
      })
      .catch((e) => logger.warn("fetch failed", { error: String(e) }))
      .finally(() => setLoadingSets(false));
  }, [workspaceId]);

  useEffect(() => {
    if (!expandedSetId || setItems[expandedSetId]) return;
    setLoadingItems(true);
    apiFetch<{ items: GoldenItem[] }>(`/api/v1/golden-sets/${expandedSetId}`)
      .then((d) => setSetItems((p) => ({ ...p, [expandedSetId]: d.items ?? [] })))
      .catch((e) => logger.warn("fetch failed", { error: String(e) }))
      .finally(() => setLoadingItems(false));
  }, [expandedSetId]);

  useEffect(() => {
    if (!selectedSetId) return;
    const params = selectedAgentId ? `?agent_id=${selectedAgentId}` : "";
    apiFetch<{ history: HistoryPoint[] }>(`/api/v1/golden-sets/${selectedSetId}/history${params}`)
      .then((d) => setHistory(d.history ?? []))
      .catch((e) => logger.warn("fetch failed", { error: String(e) }));
  }, [selectedSetId, selectedAgentId, results]);

  useEffect(() => { logsEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [logs]);

  // ── Actions ──────────────────────────────────────────────────────────

  async function importSamples() {
    setSeeding(true);
    try {
      await apiFetch<{ created: number }>("/api/v1/golden-sets/seed-samples", { method: "POST" });
      // Always refresh — datasets may already exist (created === 0) but need to be shown
      const sData = await apiFetch<{ sets: GoldenSet[] }>("/api/v1/golden-sets");
      const s = sData.sets ?? [];
      setSets(s);
      if (s[0] && !selectedSetId) { setSelectedSetId(s[0].id); setExpandedSetId(s[0].id); }
    } catch (e) { logger.warn("import samples failed", { error: String(e) }); }
    finally { setSeeding(false); }
  }

  async function createSet() {
    if (!newSetName.trim()) return;
    setCreatingSet(true);
    try {
      const r = await apiFetch<{ id: string; name: string }>("/api/v1/golden-sets", {
        method: "POST",
        json: { name: newSetName.trim(), description: newSetDesc.trim() },
      });
      const s: GoldenSet = { id: r.id, name: r.name, description: newSetDesc.trim(), item_count: 0, created_at: new Date().toISOString() };
      setSets((p) => [s, ...p]);
      setSelectedSetId(r.id);
      setExpandedSetId(r.id);
      setNewSetName(""); setNewSetDesc(""); setShowCreateSet(false);
    } catch (e) { logger.warn("create set failed", { error: String(e) }); }
    finally { setCreatingSet(false); }
  }

  async function addItem(setId: string) {
    if (!newItem.input_text.trim() || !newItem.expected_output.trim()) return;
    setAddingItem(true);
    try {
      const r = await apiFetch<{ id: string }>(`/api/v1/golden-sets/${setId}/items`, { method: "POST", json: newItem });
      const item: GoldenItem = { id: r.id, ...newItem };
      setSetItems((p) => ({ ...p, [setId]: [...(p[setId] ?? []), item] }));
      setSets((p) => p.map((s) => s.id === setId ? { ...s, item_count: s.item_count + 1 } : s));
      setNewItem({ input_text: "", expected_output: "", scoring_criteria: "" });
      setAddingItemToSet(null);
    } catch (e) { logger.warn("add item failed", { error: String(e) }); }
    finally { setAddingItem(false); }
  }

  async function deleteItem(setId: string, itemId: string) {
    await apiFetch(`/api/v1/golden-sets/${setId}/items/${itemId}`, { method: "DELETE" }).catch((e) => logger.warn("fetch failed", { error: String(e) }));
    setSetItems((p) => ({ ...p, [setId]: (p[setId] ?? []).filter((i) => i.id !== itemId) }));
    setSets((p) => p.map((s) => s.id === setId ? { ...s, item_count: Math.max(0, s.item_count - 1) } : s));
  }

  async function runEvaluation() {
    if (!selectedSetId || !selectedAgentId) return;
    setLogs([]); setResults(null); setRunning(true);
    try {
      const params = new URLSearchParams({ set_id: selectedSetId, agent_id: selectedAgentId });
      const resp = await fetch(`${getApiBase()}/api/v1/evaluations/run?${params}`, {
        headers: { Accept: "text/event-stream", Authorization: `Bearer ${getToken()}` },
      });
      const reader = resp.body?.getReader();
      if (!reader) throw new Error("no reader");
      const dec = new TextDecoder();
      // Buffer accumulates bytes across chunks — SSE events can span multiple read() calls
      let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        // SSE events are delimited by \n\n
        const events = buf.split("\n\n");
        buf = events.pop() ?? ""; // last element is the incomplete partial — keep buffering
        for (const event of events) {
          const line = event.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          try {
            const data = JSON.parse(line.slice(6));
            setLogs((p) => [...p, { id: Math.random().toString(), kind: data.kind, message: data.message, results: data.results, score: data.score, timestamp: new Date().toLocaleTimeString() }]);
            if (data.kind === "done") { setResults(data.results); setRunning(false); }
          } catch { /* malformed event — skip */ }
        }
      }
    } catch (err: any) {
      setLogs((p) => [...p, { id: "err", kind: "error", message: err.message, timestamp: new Date().toLocaleTimeString() }]);
      setRunning(false);
    }
  }

  async function autoImprove() {
    if (!selectedSetId || !selectedAgentId) return;
    setImproving(true);
    setImproveResult(null);
    try {
      const res = await apiFetch<any>("/api/v1/evaluations/improve", {
        method: "POST",
        json: { set_id: selectedSetId, agent_id: selectedAgentId },
      });
      setImproveResult(res);
      // Refresh history
      const params = new URLSearchParams({ set_id: selectedSetId, agent_id: selectedAgentId });
      const hData = await apiFetch<{ history: HistoryPoint[] }>(`/api/v1/golden-sets/${selectedSetId}/history?${params}`);
      setHistory(hData.history ?? []);
    } catch (err: any) {
      logger.warn("improve failed", { error: err.message });
    } finally {
      setImproving(false);
    }
  }

  async function loadRegression() {
    if (!selectedSetId || !selectedAgentId) return;
    setShowRegression(true);
    setLoadingRegression(true);
    try {
      const params = new URLSearchParams({ set_id: selectedSetId, agent_id: selectedAgentId });
      const res = await apiFetch<any>(`/api/v1/evaluations/regression-report?${params}`);
      setRegressionData(res);
    } catch (err: any) {
      logger.warn("regression report failed", { error: err.message });
    } finally {
      setLoadingRegression(false);
    }
  }

  // ── Derived ──────────────────────────────────────────────────────────

  const selectedSet = sets.find((s) => s.id === selectedSetId);
  const selectedAgent = agents.find((a) => a.id === selectedAgentId);
  const currentItems = selectedSetId ? (setItems[selectedSetId] ?? []) : [];
  const latestHistory = history[history.length - 1];
  const hasHistory = history.length > 0;

  // ── Empty state ──────────────────────────────────────────────────────

  if (!loadingSets && sets.length === 0) {
    return (
      <div className="flex h-full flex-col">
        <FlowPageHeader title="Evaluations" />
        <div className="flex-1 flex flex-col items-center justify-center gap-6 px-6">
          <div className="flex flex-col items-center gap-3 text-center max-w-md">
            <div className="h-16 w-16 rounded-2xl bg-flow-brand/10 border border-flow-brand/20 flex items-center justify-center">
              <Database className="h-7 w-7 text-flow-brand" />
            </div>
            <h2 className="text-lg font-semibold">No evaluation datasets yet</h2>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Evaluations let you test your agents against a set of expected outputs, track quality over time, and detect regressions automatically.
            </p>
          </div>

          <div className="flex flex-col gap-3 w-full max-w-sm">
            <Button
              className="gap-2 h-11 text-sm shadow-sm shadow-flow-brand/20"
              onClick={importSamples}
              disabled={seeding}
            >
              <Download className="h-4 w-4" />
              {seeding ? "Importing…" : "Import 8 sample datasets"}
            </Button>
            <p className="text-[11px] text-muted-foreground/60 text-center">
              Includes datasets for Research, Code Review, Data Analysis, Knowledge Curation, Daily Briefing, and Lucis health protocol agents.
            </p>
            <div className="relative flex items-center gap-2">
              <div className="flex-1 h-px bg-border/40" />
              <span className="text-[10px] text-muted-foreground/40 uppercase tracking-wide">or</span>
              <div className="flex-1 h-px bg-border/40" />
            </div>
            <Button variant="outline" className="gap-2 h-9 text-xs" onClick={() => setShowCreateSet(true)}>
              <Plus className="h-3.5 w-3.5" />
              Create your own dataset
            </Button>
          </div>

          {showCreateSet && (
            <div className="w-full max-w-sm space-y-3 rounded-xl border border-border/50 bg-card/60 p-4">
              <p className="text-sm font-medium">New dataset</p>
              <Input placeholder="Dataset name" value={newSetName} onChange={(e) => setNewSetName(e.target.value)} className="h-8 text-xs" />
              <Input placeholder="Description (optional)" value={newSetDesc} onChange={(e) => setNewSetDesc(e.target.value)} className="h-8 text-xs" />
              <div className="flex gap-2">
                <Button size="sm" className="h-7 text-xs" onClick={createSet} disabled={creatingSet || !newSetName.trim()}>
                  {creatingSet ? "Creating…" : "Create"}
                </Button>
                <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setShowCreateSet(false)}>Cancel</Button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Main layout ──────────────────────────────────────────────────────

  return (
    <div className="flex h-full flex-col">
      <FlowPageHeader title="Evaluations" />

      <div className="flex flex-1 overflow-hidden">

        {/* ══ COLUMN 1: Dataset browser ════════════════════════════════ */}
        <div className="w-72 shrink-0 border-r border-border/50 flex flex-col overflow-hidden">

          {/* Dataset list header */}
          <div className="flex items-center justify-between px-3 py-2.5 border-b border-border/40">
            <span className="text-xs font-semibold text-foreground/80 uppercase tracking-wide">Datasets</span>
            <div className="flex gap-1">
              <Button variant="ghost" size="icon" className="h-6 w-6" title="Import samples" onClick={importSamples} disabled={seeding}>
                <Download className="h-3 w-3" />
              </Button>
              <Button variant="ghost" size="icon" className="h-6 w-6" title="New dataset" onClick={() => setShowCreateSet((v) => !v)}>
                <Plus className="h-3 w-3" />
              </Button>
            </div>
          </div>

          {showCreateSet && (
            <div className="px-3 py-2.5 border-b border-border/40 bg-muted/20 space-y-2">
              <Input placeholder="Name" value={newSetName} onChange={(e) => setNewSetName(e.target.value)} className="h-7 text-xs" />
              <Input placeholder="Description" value={newSetDesc} onChange={(e) => setNewSetDesc(e.target.value)} className="h-7 text-xs" />
              <div className="flex gap-1">
                <Button size="sm" className="h-6 text-[10px] px-2" onClick={createSet} disabled={creatingSet || !newSetName.trim()}>
                  {creatingSet ? "…" : "Create"}
                </Button>
                <Button size="sm" variant="ghost" className="h-6 text-[10px] px-2" onClick={() => setShowCreateSet(false)}>Cancel</Button>
              </div>
            </div>
          )}

          {/* Dataset list */}
          <div className="flex-1 overflow-y-auto">
            {loadingSets ? (
              <div className="flex justify-center py-8">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-flow-brand border-t-transparent" />
              </div>
            ) : (
              sets.map((s) => {
                const isSelected = selectedSetId === s.id;
                const isExpanded = expandedSetId === s.id;
                const items = setItems[s.id] ?? [];
                return (
                  <div key={s.id} className={cn("border-b border-border/30 last:border-0 transition-colors", isSelected && "bg-flow-brand/5")}>
                    <button
                      type="button"
                      className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-muted/30 transition-colors"
                      onClick={() => {
                        setSelectedSetId(s.id);
                        setExpandedSetId(isExpanded ? null : s.id);
                      }}
                    >
                      {isExpanded
                        ? <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
                        : <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />}
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium truncate">{s.name}</p>
                        {s.description && <p className="text-[10px] text-muted-foreground truncate">{s.description}</p>}
                      </div>
                      <Badge variant="outline" className="text-[10px] font-mono h-4 px-1 shrink-0">{s.item_count}</Badge>
                    </button>

                    {isExpanded && (
                      <div className="px-3 pb-2 space-y-1.5">
                        {loadingItems && !setItems[s.id] ? (
                          <div className="flex justify-center py-2"><div className="h-3 w-3 animate-spin rounded-full border-2 border-flow-brand border-t-transparent" /></div>
                        ) : items.length === 0 ? (
                          <p className="text-[10px] text-muted-foreground py-1 pl-5">No items yet.</p>
                        ) : (
                          items.map((item) => (
                            <div key={item.id} className="group ml-5 rounded-lg border border-border/30 bg-card/50 p-2 space-y-1">
                              <div className="flex items-start justify-between gap-1">
                                <p className="text-[11px] font-medium text-foreground/90 line-clamp-2 flex-1">{item.input_text}</p>
                                <button onClick={() => deleteItem(s.id, item.id)} className="opacity-0 group-hover:opacity-100 shrink-0 p-0.5 text-muted-foreground hover:text-destructive transition-all">
                                  <Trash2 className="h-2.5 w-2.5" />
                                </button>
                              </div>
                              <p className="text-[10px] text-emerald-500/80 line-clamp-1">→ {item.expected_output.slice(0, 80)}{item.expected_output.length > 80 ? "…" : ""}</p>
                              {item.scoring_criteria && <p className="text-[10px] text-muted-foreground/50 italic line-clamp-1">{item.scoring_criteria}</p>}
                            </div>
                          ))
                        )}
                        {addingItemToSet === s.id ? (
                          <div className="ml-5 space-y-1.5 pt-1 border-t border-border/30">
                            <Textarea placeholder="Input question or task" value={newItem.input_text} onChange={(e) => setNewItem((n) => ({ ...n, input_text: e.target.value }))} rows={2} className="text-[11px] resize-none" />
                            <Textarea placeholder="Expected output or format" value={newItem.expected_output} onChange={(e) => setNewItem((n) => ({ ...n, expected_output: e.target.value }))} rows={2} className="text-[11px] resize-none" />
                            <Input placeholder="Scoring criteria (optional)" value={newItem.scoring_criteria} onChange={(e) => setNewItem((n) => ({ ...n, scoring_criteria: e.target.value }))} className="h-6 text-[11px]" />
                            <div className="flex gap-1">
                              <Button size="sm" className="h-6 text-[10px] px-2" onClick={() => addItem(s.id)} disabled={addingItem || !newItem.input_text.trim()}>
                                {addingItem ? "…" : "Add"}
                              </Button>
                              <Button size="sm" variant="ghost" className="h-6 text-[10px] px-2" onClick={() => setAddingItemToSet(null)}>Cancel</Button>
                            </div>
                          </div>
                        ) : (
                          <button onClick={() => { setAddingItemToSet(s.id); setNewItem({ input_text: "", expected_output: "", scoring_criteria: "" }); }} className="ml-5 flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground py-0.5 transition-colors">
                            <Plus className="h-2.5 w-2.5" /> Add item
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

        {/* ══ COLUMN 2: Agent picker ════════════════════════════════════ */}
        <div className="w-60 shrink-0 border-r border-border/50 flex flex-col overflow-hidden">
          <div className="px-3 py-2.5 border-b border-border/40">
            <span className="text-xs font-semibold text-foreground/80 uppercase tracking-wide">Agent</span>
            <p className="text-[10px] text-muted-foreground mt-0.5">Click to select</p>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {loadingSets ? (
              Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="rounded-xl border border-border/40 p-3 space-y-2">
                  <Skeleton className="h-3 w-3/4" />
                  <Skeleton className="h-2 w-1/3" />
                </div>
              ))
            ) : agents.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 px-4 py-8 text-center">
                <Bot className="h-8 w-8 text-muted-foreground/40" />
                <p className="text-xs text-muted-foreground">No agents yet.</p>
                <a href="/agents/new" className="text-xs text-flow-brand underline underline-offset-2">
                  Create an agent →
                </a>
              </div>
            ) : (
              agents.map((a) => {
                const tpl = TPL[a.template] ?? TPL["linear-3"];
                const isSelected = selectedAgentId === a.id;
                const tools = Object.entries((a.config?.tools ?? {}) as Record<string, boolean>)
                  .filter(([, v]) => v).map(([k]) => k);
                return (
                  <button
                    key={a.id}
                    type="button"
                    onClick={() => setSelectedAgentId(a.id)}
                    className={cn(
                      "w-full text-left rounded-xl border p-3 transition-all",
                      isSelected
                        ? "border-flow-brand/40 bg-flow-brand/5 shadow-sm shadow-flow-brand/10"
                        : "border-border/40 bg-card/50 hover:border-border/70 hover:bg-muted/20",
                    )}
                  >
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <p className="text-xs font-semibold leading-snug line-clamp-2">{a.name}</p>
                      <span className={cn("shrink-0 rounded-md border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide", tpl.color)}>
                        {tpl.label}
                      </span>
                    </div>
                    {tools.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {tools.slice(0, 3).map((t) => (
                          <span key={t} className="rounded px-1 py-0.5 text-[9px] bg-muted/50 text-muted-foreground border border-border/30">
                            {t.replace(/_/g, " ")}
                          </span>
                        ))}
                        {tools.length > 3 && <span className="text-[9px] text-muted-foreground/50">+{tools.length - 3}</span>}
                      </div>
                    )}
                  </button>
                );
              })
            )}
          </div>

          {/* Run button */}
          <div className="p-3 border-t border-border/40 space-y-2">
            <Button
              className="w-full gap-2 h-9 text-sm shadow-sm shadow-flow-brand/20"
              onClick={runEvaluation}
              disabled={running || improving || !selectedSetId || !selectedAgentId}
            >
              <Play className="h-3.5 w-3.5" />
              {running ? "Evaluating…" : "Run evaluation"}
            </Button>
            <Button
              variant="outline"
              className="w-full gap-2 h-9 text-sm"
              onClick={autoImprove}
              disabled={running || improving || !selectedSetId || !selectedAgentId}
            >
              <Sparkles className="h-3.5 w-3.5 text-flow-brand" />
              {improving ? "Improving..." : "Auto-Improve"}
            </Button>
            {selectedSet && selectedAgent && (
              <p className="text-[10px] text-muted-foreground/60 text-center mt-1.5">
                {selectedSet.item_count} items · {selectedAgent.name}
              </p>
            )}
          </div>
        </div>

        {/* ══ COLUMN 3: Results + logs ══════════════════════════════════ */}
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">

          {/* ── Stats bar ── */}
          {(results || hasHistory) && (
            <div className="flex items-center gap-5 px-5 py-2.5 border-b border-border/40 bg-muted/10">
              {results && (
                <>
                  <Stat label="Pass rate" value={`${(results.pass_rate * 100).toFixed(0)}%`} ok={results.pass_rate >= 0.7} />
                  <Stat label="Avg score" value={results.avg_score.toFixed(3)} />
                  <Stat label="Items" value={`${results.scored_items ?? "—"}/${results.total_items ?? "—"}`} />
                  <div className={cn("flex items-center gap-1.5 rounded-lg px-2.5 py-1 border text-xs font-medium ml-auto",
                    results.pass_rate < 0.7
                      ? "bg-red-500/8 border-red-500/20 text-red-400"
                      : "bg-emerald-500/8 border-emerald-500/20 text-emerald-400"
                  )}>
                    {results.pass_rate < 0.7
                      ? <><AlertTriangle className="h-3.5 w-3.5" /> Regression detected</>
                      : <><CheckCircle2 className="h-3.5 w-3.5" /> Agent stable</>}
                  </div>
                </>
              )}
              {hasHistory && !results && (
                <div className="flex items-center gap-4 flex-wrap flex-1">
                  <span className="text-[11px] text-muted-foreground">Last {history.length} run{history.length !== 1 ? "s" : ""}:</span>
                  {history.slice(-6).map((pt, i) => {
                    const d = new Date(pt.run_at);
                    const label = `${(d.getMonth()+1)}/${d.getDate()} ${d.getHours()}h`;
                    return (
                      <div key={pt.run_id} className="flex flex-col items-center gap-0.5" title={`${pt.version_label} — ${(pt.pass_rate*100).toFixed(0)}% pass`}>
                        <span className={cn("text-xs font-bold tabular-nums", pt.pass_rate >= 0.7 ? "text-emerald-400" : "text-red-400")}>{(pt.pass_rate * 100).toFixed(0)}%</span>
                        <span className="text-[9px] text-muted-foreground/50">{label}</span>
                      </div>
                    );
                  })}
                  <Sparkline data={history.map((p) => p.pass_rate)} uid={selectedSetId ?? "s"} />
                  {history.length >= 2 && (() => {
                    const delta = history[history.length-1].pass_rate - history[history.length-2].pass_rate;
                    return delta >= 0.01
                      ? <span className="flex items-center gap-0.5 text-[10px] text-emerald-400 font-medium"><TrendingUp className="h-3 w-3" /> +{(delta*100).toFixed(0)}%</span>
                      : delta <= -0.01
                      ? <span className="flex items-center gap-0.5 text-[10px] text-red-400 font-medium"><TrendingDown className="h-3 w-3" /> {(delta*100).toFixed(0)}%</span>
                      : null;
                  })()}
                  <Button variant="outline" size="sm" className="ml-auto h-7 text-xs" onClick={loadRegression}>
                    Regression Report
                  </Button>
                </div>
              )}
            </div>
          )}

          <div className="relative flex flex-1 overflow-hidden gap-0">

            {/* ── Live logs ── */}
            <div className="flex-1 flex flex-col p-4 gap-3 min-w-0 overflow-hidden">
              <div className="flex items-center gap-2">
                <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Live logs</span>
                {running && <div className="h-2 w-2 rounded-full bg-flow-brand animate-pulse" />}
              </div>
              <div className="flex-1 bg-[#060606] rounded-xl border border-border/20 p-4 overflow-y-auto font-mono min-h-0">
                {logs.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center gap-2 text-center">
                    <Sparkles className="h-5 w-5 text-muted-foreground/20" />
                    <p className="text-[11px] text-muted-foreground/40 italic">
                      {selectedSet && selectedAgent
                        ? `Ready to evaluate "${selectedSet.name}" with ${selectedAgent.name}`
                        : "Select a dataset and an agent, then click Run evaluation."}
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-1">
                    {logs.filter((l) => l.kind !== "done").map((log) => (
                      <div key={log.id} className="flex items-start gap-3">
                        <span className="text-muted-foreground/30 w-14 shrink-0 text-[10px] pt-px tabular-nums">{log.timestamp}</span>
                        <span className={cn("text-[11px] leading-relaxed",
                          log.kind === "error" && "text-red-400",
                          log.kind === "warning" && "text-amber-400",
                          log.kind === "success" && "text-emerald-400",
                          log.kind === "summary" && "text-sky-300 font-medium",
                          log.kind === "item_result" && (log.score !== undefined && log.score >= 0.7 ? "text-emerald-400/80" : "text-red-400/80"),
                          log.kind === "progress" && "text-zinc-500",
                          log.kind === "info" && "text-zinc-400",
                        )}>
                          {log.kind === "error" && "✗ "}
                          {log.kind === "warning" && "⚠ "}
                          {log.kind === "success" && "✓ "}
                          {log.kind === "summary" && "▶ "}
                          {log.message}
                        </span>
                      </div>
                    ))}
                    <div ref={logsEndRef} />
                  </div>
                )}
              </div>
            </div>

            {/* ── Item breakdown ── */}
            {results?.results && (
              <div className="w-72 shrink-0 border-l border-border/40 flex flex-col overflow-hidden">
                <div className="px-4 py-2.5 border-b border-border/40">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Item scores</p>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-2">
                  {results.results.map((r: any, i: number) => (
                    <div key={i} className="rounded-xl border border-border/30 bg-card/50 p-3 space-y-2">
                      <div className="flex items-center gap-2">
                        <div className={cn("shrink-0 w-9 flex flex-col items-center justify-center rounded-lg py-1 text-center",
                          r.score >= 0.7 ? "bg-emerald-500/10" : "bg-red-500/10"
                        )}>
                          <span className={cn("text-sm font-bold tabular-nums", r.score >= 0.7 ? "text-emerald-400" : "text-red-400")}>
                            {Math.round(r.score * 100)}
                          </span>
                          <span className="text-[8px] text-muted-foreground">/100</span>
                        </div>
                        <p className="text-[11px] font-medium text-foreground/90 line-clamp-2 flex-1">"{r.input_text?.slice(0, 60)}"</p>
                      </div>
                      {r.actual_output && (
                        <p className="text-[10px] text-sky-400/70 leading-relaxed line-clamp-3 bg-sky-500/5 rounded px-2 py-1.5 border border-sky-500/10">
                          {r.actual_output}
                        </p>
                      )}
                      <p className="text-[10px] text-muted-foreground leading-relaxed line-clamp-2 italic">{r.rationale}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── Auto Improve Result ── */}
            {improveResult && (
              <div className="absolute inset-0 bg-background/95 backdrop-blur z-10 flex flex-col p-6 overflow-y-auto">
                <div className="max-w-2xl mx-auto w-full space-y-6">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold flex items-center gap-2">
                      <Sparkles className="h-5 w-5 text-flow-brand" />
                      Improvement Results
                    </h2>
                    <Button variant="ghost" size="sm" onClick={() => setImproveResult(null)}>Close</Button>
                  </div>
                  
                  {improveResult.action_taken === "none" ? (
                    <div className="rounded-xl border border-border/50 bg-card p-6 text-center space-y-3">
                      <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto" />
                      <p className="font-medium text-emerald-400">{improveResult.message}</p>
                      <p className="text-sm text-muted-foreground">Score: {(improveResult.eval_score * 100).toFixed(0)}%. The agent is performing well.</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="rounded-xl border border-border/50 bg-card p-4 space-y-3">
                        <div className="flex items-center gap-2 text-sm">
                          <Badge variant="outline" className="text-amber-400 border-amber-500/20 bg-amber-500/10">Candidate Generated</Badge>
                          <span className="text-muted-foreground">Score was {(improveResult.eval_score * 100).toFixed(0)}%</span>
                        </div>
                        <p className="text-sm text-muted-foreground leading-relaxed">{improveResult.message}</p>
                        
                        {improveResult.rewrite && (
                          <div className="space-y-3 mt-4 pt-4 border-t border-border/20">
                            <div>
                              <h4 className="text-xs font-semibold text-muted-foreground mb-1.5 uppercase tracking-wide">Analysis</h4>
                              <p className="text-sm">{improveResult.rewrite.failure_analysis}</p>
                            </div>
                            <div>
                              <h4 className="text-xs font-semibold text-muted-foreground mb-1.5 uppercase tracking-wide">Changelog</h4>
                              <ul className="list-disc list-inside text-sm space-y-1 text-muted-foreground">
                                {improveResult.rewrite.changelog?.map((c: string, i: number) => (
                                  <li key={i}>{c}</li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        )}
                        
                        {improveResult.proposal_id && (
                          <div className="mt-4 pt-4 border-t border-border/20 flex items-center justify-between">
                            <p className="text-sm text-muted-foreground">A proposal has been created for this candidate.</p>
                            <a href="/proposals" className="text-sm text-flow-brand underline underline-offset-2">View Proposal →</a>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ── Regression Report ── */}
            {showRegression && (
              <div className="absolute inset-0 bg-background/95 backdrop-blur z-10 flex flex-col p-6 overflow-y-auto">
                <div className="max-w-3xl mx-auto w-full space-y-6">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold flex items-center gap-2">
                      <TrendingUp className="h-5 w-5 text-flow-brand" />
                      Regression Report
                    </h2>
                    <Button variant="ghost" size="sm" onClick={() => setShowRegression(false)}>Close</Button>
                  </div>

                  {loadingRegression ? (
                    <div className="flex justify-center py-12"><div className="h-6 w-6 animate-spin rounded-full border-2 border-flow-brand border-t-transparent" /></div>
                  ) : regressionData ? (
                    <div className="space-y-6">
                      <div className="grid grid-cols-3 gap-4">
                        <div className="rounded-xl border border-border/50 bg-card p-4">
                          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">Trend</p>
                          <p className="text-lg font-medium capitalize">{regressionData.trend?.replace('_', ' ')}</p>
                        </div>
                        <div className="rounded-xl border border-border/50 bg-card p-4">
                          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">Current Score</p>
                          <p className="text-lg font-medium">{regressionData.curr_avg ? (regressionData.curr_avg * 100).toFixed(0) : 0}%</p>
                        </div>
                        <div className="rounded-xl border border-border/50 bg-card p-4">
                          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">Delta</p>
                          <p className={cn("text-lg font-medium", regressionData.avg_delta >= 0 ? "text-emerald-400" : "text-red-400")}>
                            {regressionData.avg_delta >= 0 ? "+" : ""}{regressionData.avg_delta ? (regressionData.avg_delta * 100).toFixed(1) : 0}%
                          </p>
                        </div>
                      </div>

                      <div className="space-y-4">
                        {regressionData.regressed && regressionData.regressed.length > 0 && (
                          <div className="space-y-2">
                            <h3 className="text-sm font-semibold text-red-400 flex items-center gap-1.5"><TrendingDown className="h-4 w-4" /> Regressed Items ({regressionData.regressed.length})</h3>
                            {regressionData.regressed.map((item: any) => (
                              <div key={item.item_id} className="rounded-lg border border-red-500/20 bg-red-500/5 p-3 flex justify-between items-center">
                                <span className="text-sm font-mono text-muted-foreground">{item.item_id.split('-')[0]}</span>
                                <div className="flex items-center gap-3">
                                  <span className="text-sm">{(item.prev_score * 100).toFixed(0)}% → {(item.curr_score * 100).toFixed(0)}%</span>
                                  <Badge variant="outline" className="text-red-400 border-red-500/30">{(item.delta * 100).toFixed(0)}%</Badge>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                        
                        {regressionData.improved && regressionData.improved.length > 0 && (
                          <div className="space-y-2">
                            <h3 className="text-sm font-semibold text-emerald-400 flex items-center gap-1.5"><TrendingUp className="h-4 w-4" /> Improved Items ({regressionData.improved.length})</h3>
                            {regressionData.improved.map((item: any) => (
                              <div key={item.item_id} className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3 flex justify-between items-center">
                                <span className="text-sm font-mono text-muted-foreground">{item.item_id.split('-')[0]}</span>
                                <div className="flex items-center gap-3">
                                  <span className="text-sm">{(item.prev_score * 100).toFixed(0)}% → {(item.curr_score * 100).toFixed(0)}%</span>
                                  <Badge variant="outline" className="text-emerald-400 border-emerald-500/30">+{(item.delta * 100).toFixed(0)}%</Badge>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">No data available.</p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <div className="flex flex-col">
      <span className="text-[9px] text-muted-foreground uppercase tracking-wide">{label}</span>
      <span className={cn("text-lg font-light tabular-nums leading-tight",
        ok === true ? "text-emerald-400" : ok === false ? "text-red-400" : "text-foreground"
      )}>{value}</span>
    </div>
  );
}
