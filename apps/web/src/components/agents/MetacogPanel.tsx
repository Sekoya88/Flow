"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BarChart3,
  Brain,
  Crosshair,
  Loader2,
  Sparkles,
  Target,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
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
          <Target className="h-3.5 w-3.5 text-flow-brand" />
          <span className="text-xs font-medium text-foreground">Confidence trend</span>
        </div>
        <div className="rounded-xl border border-border/40 bg-muted/10 p-3">
          <ConfidenceTrend data={data.confidence_trend} height={52} />
        </div>
      </div>

      {/* Grade distribution */}
      {gradeEntries.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-3.5 w-3.5 text-flow-brand" />
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
    </div>
  );
}
