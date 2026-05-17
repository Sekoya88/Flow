"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  BarChart2,
  CheckCircle2,
  Loader2,
  Plus,
  Trophy,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { track } from "@/lib/analytics";
import { apiFetch } from "@/lib/api";
import { logger } from "@/lib/logger";
import { cn } from "@/lib/utils";

type AgentRow = { id: string; name: string };
type GoldenSet = { id: string; name: string; item_count: number };
type ABTest = {
  id: string;
  status: string;
  agent_a: string;
  agent_b: string;
  golden_set: string;
  created_at: string;
};

function statusBadge(status: string) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "rounded-md px-2 py-0 text-[10px] font-mono",
        status === "completed" && "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
        status === "running" && "border-flow-streaming/30 bg-flow-streaming/10 text-flow-amber",
        status === "pending" && "border-amber-500/30 bg-amber-500/10 text-amber-400",
      )}
    >
      {status === "running" && (
        <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-flow-streaming animate-pulse" />
      )}
      {status}
    </Badge>
  );
}

export default function ABTestPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [sets, setSets] = useState<GoldenSet[]>([]);
  const [tests, setTests] = useState<ABTest[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [agentA, setAgentA] = useState("");
  const [agentB, setAgentB] = useState("");
  const [goldenSet, setGoldenSet] = useState("");
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const me = await apiFetch<{ workspaces: { id: string }[] }>("/api/v1/auth/me");
      const wsId = me.workspaces[0]?.id;
      if (!wsId) return;
      const [agentsData, setsData, testsData] = await Promise.all([
        apiFetch<{ agents: AgentRow[] }>(`/api/v1/workspaces/${wsId}/agents`),
        apiFetch<{ sets: GoldenSet[] }>("/api/v1/golden-sets"),
        apiFetch<{ tests: ABTest[] }>("/api/v1/ab-tests"),
      ]);
      setAgents(agentsData.agents ?? []);
      setSets(setsData.sets ?? []);
      setTests(testsData.tests ?? []);
      if (agentsData.agents[0]) setAgentA(agentsData.agents[0].id);
      if (agentsData.agents[1]) setAgentB(agentsData.agents[1].id);
      if (setsData.sets[0]) setGoldenSet(setsData.sets[0].id);
    } catch (e) {
      logger.warn("ab test load", { error: String(e) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const createTest = useCallback(async () => {
    if (!agentA || !agentB || !goldenSet || agentA === agentB) return;
    setCreating(true);
    try {
      await apiFetch("/api/v1/ab-tests", {
        method: "POST",
        json: { golden_set_id: goldenSet, agent_a_id: agentA, agent_b_id: agentB },
      });
      track("ab_test_started", { agent_a: agentA, agent_b: agentB, golden_set: goldenSet });
      setShowForm(false);
      void load();
    } finally {
      setCreating(false);
    }
  }, [agentA, agentB, goldenSet, load]);

  return (
    <div className="mx-auto w-full max-w-5xl space-y-8 px-4 pb-10 animate-fade-in">
      <FlowPageHeader
        eyebrow={
          <Badge variant="outline" className="gap-1 font-mono text-[10px] uppercase tracking-wide">
            <BarChart2 className="h-3 w-3" />
            A/B Testing
          </Badge>
        }
        title="A/B Tests"
        description="Compare two agents head-to-head on a shared golden set. LLM-judge scores each response and declares a winner."
        actions={
          <Button onClick={() => setShowForm(true)} className="gap-1.5">
            <Plus className="h-4 w-4" />
            New test
          </Button>
        }
      />

      {/* Create form */}
      {showForm && (
        <div className="rounded-[6px] border border-flow-amber/20 bg-flow-amber/5 p-6 space-y-5 animate-slide-up">
          <p className="text-sm font-semibold text-foreground">New A/B Test</p>
          <div className="grid grid-cols-[1fr_auto_1fr] gap-4 items-center">
            <div className="space-y-2">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Agent A</p>
              <Select value={agentA} onValueChange={(v) => { if (v) setAgentA(v); }}>
                <SelectTrigger className="h-9 text-sm"><SelectValue placeholder="Select agent A" /></SelectTrigger>
                <SelectContent>{agents.map((a) => <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="flex flex-col items-center gap-1 pt-5">
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
              <span className="text-[10px] text-muted-foreground">vs</span>
              <ArrowRight className="h-4 w-4 text-muted-foreground rotate-180" />
            </div>
            <div className="space-y-2">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Agent B</p>
              <Select value={agentB} onValueChange={(v) => { if (v) setAgentB(v); }}>
                <SelectTrigger className="h-9 text-sm"><SelectValue placeholder="Select agent B" /></SelectTrigger>
                <SelectContent>{agents.map((a) => <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-2">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Golden Set</p>
            <Select value={goldenSet} onValueChange={(v) => { if (v) setGoldenSet(v); }}>
              <SelectTrigger className="h-9 text-sm max-w-sm"><SelectValue placeholder="Select golden set" /></SelectTrigger>
              <SelectContent>
                {sets.length === 0 ? (
                  <SelectItem value="" disabled>No golden sets available</SelectItem>
                ) : (
                  sets.map((s) => (
                    <SelectItem key={s.id} value={s.id}>{s.name} ({s.item_count} items)</SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>
          {agentA === agentB && agentA && (
            <p className="text-xs text-amber-500">Please select two different agents.</p>
          )}
          <div className="flex gap-2">
            <Button size="sm" onClick={() => void createTest()} disabled={creating || !agentA || !agentB || !goldenSet || agentA === agentB} className="gap-1.5">
              {creating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
              {creating ? "Starting…" : "Start test"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
          </div>
        </div>
      )}

      {/* Tests list */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
        </div>
      ) : tests.length === 0 ? (
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <BarChart2 className="h-10 w-10 text-muted-foreground/30" />
          <p className="text-sm text-muted-foreground max-w-xs">No A/B tests yet. Create your first test to compare agents side-by-side.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {tests.map((test) => (
            <button
              key={test.id}
              onClick={() => router.push(`/agents/ab-test/${test.id}`)}
              className={cn(
                "w-full flex items-center gap-4 rounded-xl border border-flow-800 bg-card px-4 py-3.5",
                "text-left transition-all hover:border-border hover:bg-card/80 hover:-translate-y-0.5 hover:shadow-md",
              )}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium text-foreground">{test.agent_a}</span>
                  <span className="text-muted-foreground">vs</span>
                  <span className="text-sm font-medium text-foreground">{test.agent_b}</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  {test.golden_set} · {new Date(test.created_at).toLocaleDateString()}
                </p>
              </div>
              {statusBadge(test.status)}
              <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
