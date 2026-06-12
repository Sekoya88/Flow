"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BarChart3,
  Brain,
  Crosshair,
  Dna,
  Loader2,
  Sparkles,
  Target,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfidenceTrend } from "./ConfidenceTrend";
import { apiFetch } from "@/lib/api";
import { logger } from "@/lib/logger";
import { cn } from "@/lib/utils";

interface MetacogPanelProps {
  agentId: string;
  className?: string;
}

type StatsData = {
  total_runs: number;
  avg_confidence: number;
  grade_distribution: Record<string, number>;
  confidence_trend: Array<{ confidence: number; created_at: string; execution_id: string }>;
  last_run_at: string | null;
};

const GRADE_COLORS = [
  "", // 0 — unused
  "bg-rose-500",     // 1
  "bg-orange-400",   // 2
  "bg-amber-400",    // 3
  "bg-emerald-400",  // 4
  "bg-emerald-500",  // 5
];

const GRADE_LABELS = ["", "Poor", "Below avg", "Average", "Good", "Excellent"];

type BanditArm = {
  skill_id: string;
  skill_name: string;
  mean: number;
  total_pulls: number;
  total_reward: number;
};

type RlEpisode = {
  id: string;
  mutation_type: string | null;
  reward_before: number;
  reward_after: number;
  reward_delta: number;
  promoted: boolean;
  created_at: string | null;
};

type EvolveResult = {
  cycle_status: string;
  current_score: number | null;
  candidate_score: number | null;
  mutation_type: string | null;
};

function EvolutionSection({ agentId }: { agentId: string }) {
  const [arms, setArms] = useState<BanditArm[]>([]);
  const [episodes, setEpisodes] = useState<RlEpisode[]>([]);
  const [evolving, setEvolving] = useState(false);
  const [lastResult, setLastResult] = useState<EvolveResult | null>(null);

  const load = useCallback(() => {
    apiFetch<{ arms: BanditArm[] }>(`/api/v1/agents/${agentId}/bandit`)
      .then((r) => setArms(r.arms ?? []))
      .catch(() => {});
    apiFetch<{ episodes: RlEpisode[] }>(`/api/v1/agents/${agentId}/rl-episodes?limit=5`)
      .then((r) => setEpisodes(r.episodes ?? []))
      .catch(() => {});
  }, [agentId]);

  useEffect(() => {
    load();
  }, [load]);

  async function evolve() {
    setEvolving(true);
    try {
      const r = await apiFetch<EvolveResult>(`/api/v1/agents/${agentId}/evolve`, {
        method: "POST",
        json: {},
      });
      setLastResult(r);
      if (r.cycle_status === "promoted") toast.success("Evolution: candidate promoted");
      else toast.info(`Evolution cycle: ${r.cycle_status}`);
      load();
    } catch (e) {
      logger.warn("evolve failed", { agentId, error: String(e) });
      toast.error("Evolution cycle failed");
    } finally {
      setEvolving(false);
    }
  }

  return (
    <div className="space-y-3 border-t border-flow-800 pt-4">
      <div className="flex items-center gap-2">
        <Dna className="h-3.5 w-3.5 text-flow-violet" />
        <span className="text-xs font-medium text-foreground">Genome evolution</span>
        <Button
          size="sm"
          disabled={evolving}
          onClick={() => void evolve()}
          className="ml-auto h-6 gap-1 px-2 text-[10px]"
        >
          {evolving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
          {evolving ? "Evolving…" : "Evolve"}
        </Button>
      </div>

      {lastResult && (
        <div className="rounded-lg border border-flow-800 bg-muted/10 px-3 py-2 font-mono text-[10px] text-muted-foreground">
          Cycle: <span className="text-foreground">{lastResult.cycle_status}</span>
          {lastResult.mutation_type && <> · mutation: {lastResult.mutation_type}</>}
          {lastResult.current_score != null && lastResult.candidate_score != null && (
            <> · {lastResult.current_score.toFixed(3)} → {lastResult.candidate_score.toFixed(3)}</>
          )}
        </div>
      )}

      {arms.length > 0 && (
        <div className="space-y-1">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Skill bandit (Thompson)</p>
          {arms.slice(0, 5).map((a) => (
            <div key={a.skill_id} className="flex items-center gap-2">
              <span className="min-w-0 flex-1 truncate font-mono text-[10px] text-foreground/80">{a.skill_name}</span>
              <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted/30">
                <div className="h-full rounded-full bg-flow-violet" style={{ width: `${Math.min(a.mean * 100, 100)}%` }} />
              </div>
              <span className="w-10 shrink-0 text-right font-mono text-[10px] tabular-nums text-muted-foreground">
                {(a.mean * 100).toFixed(0)}%
              </span>
              <span className="w-12 shrink-0 text-right font-mono text-[9px] text-muted-foreground/60">
                {a.total_pulls} pulls
              </span>
            </div>
          ))}
        </div>
      )}

      {episodes.length > 0 && (
        <div className="space-y-1">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Recent RL episodes</p>
          {episodes.map((ep) => (
            <div key={ep.id} className="flex items-center gap-2 font-mono text-[10px]">
              <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", ep.promoted ? "bg-emerald-500" : "bg-flow-700")} />
              <span className="min-w-0 flex-1 truncate text-foreground/70">{ep.mutation_type ?? "mutation"}</span>
              <span className={cn("shrink-0 tabular-nums", ep.reward_delta > 0 ? "text-emerald-400" : ep.reward_delta < 0 ? "text-red-400" : "text-muted-foreground")}>
                {ep.reward_delta >= 0 ? "+" : ""}{ep.reward_delta.toFixed(3)}
              </span>
              {ep.promoted && <Badge variant="outline" className="h-4 shrink-0 border-emerald-500/40 px-1 text-[8px] text-emerald-400">promoted</Badge>}
            </div>
          ))}
        </div>
      )}

      {arms.length === 0 && episodes.length === 0 && !lastResult && (
        <p className="text-[10px] text-muted-foreground">
          No evolution data yet. Run an evolution cycle to mutate the agent genome against its golden set.
        </p>
      )}
    </div>
  );
}

export function MetacogPanel({ agentId, className }: MetacogPanelProps) {
  const [data, setData] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    apiFetch<StatsData>(`/api/v1/agents/${agentId}/stats`)
      .then(setData)
      .catch((e) => logger.warn("metacog stats load failed", { agentId, error: String(e) }))
      .finally(() => setLoading(false));
  }, [agentId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className={cn("flex items-center justify-center py-8", className)}>
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!data || data.total_runs === 0) {
    return (
      <div className={cn("flex flex-col items-center gap-3 py-8 text-center", className)}>
        <Brain className="h-8 w-8 text-muted-foreground/30" />
        <p className="text-xs text-muted-foreground">
          No executions yet. Run the agent to see metacognition data.
        </p>
      </div>
    );
  }

  const gradeEntries = Object.entries(data.grade_distribution)
    .map(([g, c]) => ({ grade: parseInt(g), count: c }))
    .sort((a, b) => a.grade - b.grade);
  const maxGradeCount = Math.max(...gradeEntries.map((e) => e.count), 1);

  return (
    <div className={cn("space-y-5", className)}>
      {/* Confidence trend */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Target className="h-3.5 w-3.5 text-flow-violet" />
          <span className="text-xs font-medium text-foreground">Confidence trend</span>
        </div>
        <div className="rounded-xl border border-flow-800 bg-muted/10 p-3">
          <ConfidenceTrend data={data.confidence_trend} height={52} />
        </div>
      </div>

      {/* Grade distribution */}
      {gradeEntries.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-3.5 w-3.5 text-flow-violet" />
            <span className="text-xs font-medium text-foreground">Grade distribution</span>
            <span className="text-[10px] text-muted-foreground ml-auto">
              {gradeEntries.reduce((s, e) => s + e.count, 0)} graded
            </span>
          </div>
          <div className="space-y-1.5">
            {[1, 2, 3, 4, 5].map((grade) => {
              const entry = gradeEntries.find((e) => e.grade === grade);
              const count = entry?.count ?? 0;
              const pct = (count / maxGradeCount) * 100;
              return (
                <div key={grade} className="flex items-center gap-2">
                  <span className="w-5 text-[10px] font-mono tabular-nums text-muted-foreground text-right">
                    {grade}
                  </span>
                  <div className="flex-1 h-4 bg-muted/20 rounded-md overflow-hidden">
                    <div
                      className={cn(
                        "h-full rounded-md transition-all duration-500",
                        GRADE_COLORS[grade],
                      )}
                      style={{ width: `${pct}%`, opacity: count > 0 ? 0.8 : 0 }}
                    />
                  </div>
                  <span className="w-6 text-[10px] font-mono tabular-nums text-muted-foreground">
                    {count}
                  </span>
                </div>
              );
            })}
          </div>
          <p className="text-[10px] text-muted-foreground text-center">
            {GRADE_LABELS[gradeEntries[gradeEntries.length - 1]?.grade || 3] ?? "Average"} performance
          </p>
        </div>
      )}

      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg border border-border/30 bg-muted/10 px-3 py-2 text-center">
          <p className="text-[9px] uppercase tracking-wide text-muted-foreground">Total runs</p>
          <p className="font-mono text-base font-semibold tabular-nums">{data.total_runs}</p>
        </div>
        <div className="rounded-lg border border-border/30 bg-muted/10 px-3 py-2 text-center">
          <p className="text-[9px] uppercase tracking-wide text-muted-foreground">Avg confidence</p>
          <p className="font-mono text-base font-semibold tabular-nums">
            {(data.avg_confidence * 100).toFixed(0)}%
          </p>
        </div>
      </div>

      <EvolutionSection agentId={agentId} />
    </div>
  );
}
