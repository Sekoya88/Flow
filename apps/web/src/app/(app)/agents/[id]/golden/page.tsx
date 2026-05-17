"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  BarChart3,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Loader2,
  PlayCircle,
  Plus,
  Target,
  Trash2,
  Trophy,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { track } from "@/lib/analytics";
import { apiFetch } from "@/lib/api";
import { logger } from "@/lib/logger";
import { cn } from "@/lib/utils";

type GoldenItem = {
  id: string;
  input_text: string;
  expected_output: string;
  scoring_criteria: string;
};

type ResultRow = {
  id: string;
  item_id: string;
  agent_id: string;
  agent_version_label: string | null;
  score: number | null;
  rationale: string | null;
  actual_output: string | null;
  input_text: string;
  expected_output: string;
};

type AgentRow = { id: string; name: string };

function scoreColor(score: number | null): string {
  if (score === null) return "text-muted-foreground";
  if (score >= 0.8) return "text-emerald-500";
  if (score >= 0.5) return "text-amber-500";
  return "text-rose-500";
}

function scoreIcon(score: number | null) {
  if (score === null) return null;
  if (score >= 0.7) return <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />;
  return <XCircle className="h-3.5 w-3.5 text-rose-500" />;
}

export default function GoldenSetPage() {
  const params = useParams<{ id: string }>();
  const setId = params.id;
  const router = useRouter();

  const [items, setItems] = useState<GoldenItem[]>([]);
  const [results, setResults] = useState<ResultRow[]>([]);
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [setName, setSetName] = useState<string>("");
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [evaluating, setEvaluating] = useState(false);
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const [aggregate, setAggregate] = useState<{ avg_score: number; pass_rate: number; count: number; min_score: number } | null>(null);

  // New item form
  const [newInput, setNewInput] = useState("");
  const [newExpected, setNewExpected] = useState("");
  const [newCriteria, setNewCriteria] = useState("");
  const [addingItem, setAddingItem] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const me = await apiFetch<{ workspaces: { id: string }[] }>("/api/v1/auth/me");
      const wsId = me.workspaces[0]?.id;
      if (!wsId) return;

      const [setData, resultsData, agentsData] = await Promise.all([
        apiFetch<{ items: GoldenItem[] }>(`/api/v1/golden-sets/${setId}`),
        apiFetch<{ results: ResultRow[]; aggregate: typeof aggregate }>(`/api/v1/golden-sets/${setId}/results`),
        apiFetch<{ agents: AgentRow[] }>(`/api/v1/workspaces/${wsId}/agents`),
      ]);

      setItems(setData.items ?? []);
      setResults(resultsData.results ?? []);
      setAggregate(resultsData.aggregate ?? null);
      setAgents(agentsData.agents ?? []);
      if (agentsData.agents?.[0]) setSelectedAgent(agentsData.agents[0].id);
    } catch (e) {
      logger.warn("golden set load failed", { error: String(e) });
    } finally {
      setLoading(false);
    }
  }, [setId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const addItem = useCallback(async () => {
    if (!newInput.trim() || !newExpected.trim()) return;
    setAddingItem(true);
    try {
      await apiFetch(`/api/v1/golden-sets/${setId}/items`, {
        method: "POST",
        json: {
          input_text: newInput.trim(),
          expected_output: newExpected.trim(),
          scoring_criteria: newCriteria.trim(),
        },
      });
      setNewInput(""); setNewExpected(""); setNewCriteria(""); setShowAddForm(false);
      void loadData();
    } finally {
      setAddingItem(false);
    }
  }, [setId, newInput, newExpected, newCriteria, loadData]);

  const deleteItem = useCallback(async (itemId: string) => {
    await apiFetch(`/api/v1/golden-sets/${setId}/items/${itemId}`, { method: "DELETE" });
    void loadData();
  }, [setId, loadData]);

  const triggerEvaluate = useCallback(async () => {
    if (!selectedAgent) return;
    setEvaluating(true);
    try {
      await apiFetch(`/api/v1/golden-sets/${setId}/evaluate`, {
        method: "POST",
        json: { agent_id: selectedAgent },
      });
      track("golden_set_evaluated", { golden_set_id: setId, agent_id: selectedAgent });
      // Poll for results after a delay
      setTimeout(() => { void loadData(); setEvaluating(false); }, 5000);
    } catch {
      setEvaluating(false);
    }
  }, [setId, selectedAgent, loadData]);

  // Group results by item
  const resultsByItem = new Map<string, ResultRow>();
  for (const r of results) resultsByItem.set(r.item_id, r);

  return (
    <div className="mx-auto w-full max-w-5xl space-y-8 px-4 pb-10 animate-fade-in">
      <FlowPageHeader
        eyebrow={
          <button onClick={() => router.push("/agents")} className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors text-xs">
            <ArrowLeft className="h-3 w-3" />
            Back to agents
          </button>
        }
        title="Golden Set"
        description="Test cases for evaluating agent quality. Add input/expected pairs and run evaluations to score your agent."
        actions={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowAddForm(true)} className="gap-1.5">
              <Plus className="h-3.5 w-3.5" />
              Add test case
            </Button>
          </div>
        }
      />

      {/* Aggregate stats */}
      {aggregate && aggregate.count > 0 && (
        <div className="grid grid-cols-4 gap-3 animate-slide-up">
          {[
            { label: "Evaluated", value: aggregate.count, icon: Target },
            { label: "Avg score", value: `${(aggregate.avg_score * 100).toFixed(0)}%`, icon: BarChart3 },
            { label: "Pass rate ≥70%", value: `${(aggregate.pass_rate * 100).toFixed(0)}%`, icon: Trophy },
            { label: "Min score", value: `${(aggregate.min_score * 100).toFixed(0)}%`, icon: BarChart3 },
          ].map(({ label, value, icon: Icon }) => (
            <div key={label} className="rounded-xl border border-flow-800 bg-card p-4 text-center">
              <Icon className="h-4 w-4 text-flow-amber mx-auto mb-2" />
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="font-mono text-xl font-bold tabular-nums mt-0.5">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Evaluate bar */}
      <div className="flex items-center gap-3 rounded-xl border border-flow-800 bg-card px-4 py-3">
        <span className="text-sm text-muted-foreground shrink-0">Evaluate with</span>
        <Select value={selectedAgent} onValueChange={(v) => { if (v) setSelectedAgent(v); }}>
          <SelectTrigger className="h-8 text-xs max-w-xs">
            <SelectValue placeholder="Select agent" />
          </SelectTrigger>
          <SelectContent>
            {agents.map((a) => (
              <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          size="sm"
          className="gap-1.5 ml-auto"
          disabled={evaluating || !selectedAgent || items.length === 0}
          onClick={() => void triggerEvaluate()}
        >
          {evaluating ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <PlayCircle className="h-3.5 w-3.5" />
          )}
          {evaluating ? "Evaluating…" : "Run evaluation"}
        </Button>
      </div>

      {/* Add form */}
      {showAddForm && (
        <div className="rounded-xl border border-flow-amber/20 bg-flow-amber/5 p-5 space-y-3 animate-slide-up">
          <p className="text-sm font-medium text-foreground">New test case</p>
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Input / Question</Label>
            <Input value={newInput} onChange={(e) => setNewInput(e.target.value)} placeholder="e.g. What is LangGraph?" className="text-sm" />
          </div>
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Expected output</Label>
            <textarea
              value={newExpected}
              onChange={(e) => setNewExpected(e.target.value)}
              placeholder="The expected answer or key facts that must be present…"
              rows={3}
              className="w-full resize-none rounded-lg border border-flow-800 bg-card/80 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-flow-amber/30"
            />
          </div>
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Scoring criteria (optional)</Label>
            <Input value={newCriteria} onChange={(e) => setNewCriteria(e.target.value)} placeholder="e.g. Must mention LangGraph nodes and edges" className="text-sm" />
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => void addItem()} disabled={addingItem || !newInput || !newExpected} className="gap-1.5">
              {addingItem ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
              {addingItem ? "Adding…" : "Add"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setShowAddForm(false)}>Cancel</Button>
          </div>
        </div>
      )}

      {/* Items list */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-16 rounded-xl" />)}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <Target className="h-10 w-10 text-muted-foreground/30" />
          <p className="text-sm text-muted-foreground max-w-xs">Add test cases to start evaluating your agent quality systematically.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item, idx) => {
            const result = resultsByItem.get(item.id);
            const isExpanded = expandedItem === item.id;
            return (
              <div key={item.id} className="rounded-xl border border-flow-800 bg-card overflow-hidden">
                <button
                  type="button"
                  onClick={() => setExpandedItem(isExpanded ? null : item.id)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/20 transition-colors"
                >
                  <span className="text-[10px] font-mono text-muted-foreground/50 tabular-nums w-5 shrink-0">
                    {idx + 1}
                  </span>
                  {isExpanded ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />}
                  <span className="text-sm text-foreground flex-1 truncate">{item.input_text}</span>
                  {result?.score !== undefined && (
                    <div className="flex items-center gap-1.5 shrink-0">
                      {scoreIcon(result.score)}
                      <span className={cn("font-mono text-sm tabular-nums font-semibold", scoreColor(result.score))}>
                        {result.score !== null ? `${(result.score * 100).toFixed(0)}%` : "—"}
                      </span>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); void deleteItem(item.id); }}
                    className="ml-2 text-muted-foreground/40 hover:text-rose-500 transition-colors shrink-0"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </button>

                {isExpanded && (
                  <div className="border-t border-flow-800 px-4 py-3 space-y-3 animate-slide-up">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Expected</p>
                        <p className="text-xs text-foreground/80 leading-relaxed">{item.expected_output}</p>
                      </div>
                      {result?.actual_output && (
                        <div>
                          <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Actual</p>
                          <p className="text-xs text-foreground/80 leading-relaxed">{result.actual_output}</p>
                        </div>
                      )}
                    </div>
                    {result?.rationale && (
                      <div className={cn(
                        "rounded-lg px-3 py-2 text-xs italic text-muted-foreground",
                        (result.score ?? 0) >= 0.7 ? "bg-emerald-500/5 border border-emerald-500/10" : "bg-rose-500/5 border border-rose-500/10",
                      )}>
                        🧑‍⚖️ {result.rationale}
                      </div>
                    )}
                    {item.scoring_criteria && (
                      <p className="text-[10px] text-muted-foreground">
                        <span className="font-medium">Criteria:</span> {item.scoring_criteria}
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
