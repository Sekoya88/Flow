"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Bot, GitCompare, Trophy } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { apiFetch } from "@/lib/api";
import { logger } from "@/lib/logger";
import { cn } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────

type AgentInfo = { name: string; version: string | null };

type ItemResult = {
  item_id: string;
  agent_label: "A" | "B";
  score: number | null;
  rationale: string | null;
  actual_output: string;
  input_text: string;
};

type ABTestDetail = {
  id: string;
  status: string;
  agent_a: AgentInfo;
  agent_b: AgentInfo;
  golden_set: string;
  aggregate: { agent_a_avg: number; agent_b_avg: number; winner: "A" | "B" };
  results: ItemResult[];
  created_at: string;
};

// ── Helpers ───────────────────────────────────────────────────────────

type PairedItem = {
  input_text: string;
  a: ItemResult | null;
  b: ItemResult | null;
};

function pairResults(results: ItemResult[]): PairedItem[] {
  const map = new Map<string, PairedItem>();
  for (const r of results) {
    if (!map.has(r.input_text)) {
      map.set(r.input_text, { input_text: r.input_text, a: null, b: null });
    }
    const entry = map.get(r.input_text)!;
    if (r.agent_label === "A") entry.a = r;
    else entry.b = r;
  }
  return Array.from(map.values());
}

function statusVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  if (status === "completed") return "default";
  if (status === "running") return "secondary";
  if (status === "failed") return "destructive";
  return "outline";
}

// ── Component ─────────────────────────────────────────────────────────

export default function ABTestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [test, setTest] = useState<ABTestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    apiFetch<ABTestDetail>(`/api/v1/ab-tests/${id}`)
      .then(setTest)
      .catch((e) => {
        logger.warn("ab test detail load failed", { error: String(e) });
        setError("Could not load A/B test.");
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-5xl px-4 py-8 space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error || !test) {
    return (
      <div className="mx-auto w-full max-w-5xl px-4 py-8">
        <p className="text-sm text-destructive">{error ?? "Test not found."}</p>
        <Button variant="outline" size="sm" className="mt-4" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-2" /> Back
        </Button>
      </div>
    );
  }

  const paired = pairResults(test.results);
  const { aggregate } = test;

  return (
    <div className="flex flex-col min-h-screen">
      <FlowPageHeader
        leading={<GitCompare className="h-4 w-4 text-muted-foreground" />}
        title="A/B Test Results"
        description={`${test.agent_a.name} vs ${test.agent_b.name} · ${test.golden_set}`}
      />

      <div className="mx-auto w-full max-w-5xl px-4 py-6 space-y-6">
        {/* Back + status */}
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => router.push("/agents/ab-test")}>
            <ArrowLeft className="h-4 w-4 mr-1" /> Back
          </Button>
          <Badge variant={statusVariant(test.status)} className="capitalize">
            {test.status}
          </Badge>
          <span className="text-xs text-muted-foreground ml-auto">
            {new Date(test.created_at).toLocaleString()}
          </span>
        </div>

        {/* Scorecards */}
        <div className="grid grid-cols-2 gap-4">
          {(["A", "B"] as const).map((label) => {
            const agent = label === "A" ? test.agent_a : test.agent_b;
            const avg = label === "A" ? aggregate.agent_a_avg : aggregate.agent_b_avg;
            const isWinner = aggregate.winner === label && test.status === "completed";
            return (
              <div
                key={label}
                className={cn(
                  "rounded-[6px] border p-5 space-y-2 transition-all",
                  isWinner
                    ? "border-flow-violet/40 bg-flow-violet/5 shadow-none/10"
                    : "border-flow-800 bg-card",
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-muted/60 border border-flow-800">
                      <Bot className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold">{agent.name}</p>
                      {agent.version && (
                        <p className="text-[10px] text-muted-foreground">{agent.version}</p>
                      )}
                    </div>
                  </div>
                  {isWinner && (
                    <div className="flex items-center gap-1 text-flow-violet text-xs font-semibold">
                      <Trophy className="h-3.5 w-3.5" /> Winner
                    </div>
                  )}
                </div>
                <div className="flex items-end gap-1">
                  <span className="text-3xl font-bold tabular-nums">
                    {(avg * 10).toFixed(1)}
                  </span>
                  <span className="text-sm text-muted-foreground pb-0.5">/ 10</span>
                </div>
                <p className="text-[11px] text-muted-foreground">Agent {label} avg score</p>
              </div>
            );
          })}
        </div>

        {/* Winner banner */}
        {test.status === "completed" && (
          <div className="rounded-xl border border-flow-violet/20 bg-flow-violet/5 px-4 py-3 flex items-center gap-3">
            <Trophy className="h-5 w-5 text-flow-violet shrink-0" />
            <p className="text-sm font-medium">
              Agent {aggregate.winner} wins with an average score of{" "}
              <strong>
                {(aggregate.winner === "A" ? aggregate.agent_a_avg * 10 : aggregate.agent_b_avg * 10).toFixed(1)}
              </strong>
              /10 vs{" "}
              {((aggregate.winner === "A" ? aggregate.agent_b_avg : aggregate.agent_a_avg) * 10).toFixed(1)}/10
            </p>
          </div>
        )}

        {/* Per-item results table */}
        {paired.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-sm font-semibold">Per-item results</h2>
            <div className="rounded-xl border border-flow-800 overflow-hidden">
              {/* Header */}
              <div className="grid grid-cols-[1fr_1fr_1fr] border-b border-flow-800 bg-muted/30">
                <div className="px-4 py-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Input</div>
                <div className="px-4 py-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground border-l border-border/30">
                  Agent A — {test.agent_a.name}
                </div>
                <div className="px-4 py-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground border-l border-border/30">
                  Agent B — {test.agent_b.name}
                </div>
              </div>
              {/* Rows */}
              {paired.map((item, i) => (
                <div
                  key={i}
                  className={cn(
                    "grid grid-cols-[1fr_1fr_1fr]",
                    i !== 0 && "border-t border-border/30",
                  )}
                >
                  {/* Input */}
                  <div className="px-4 py-3 text-xs text-muted-foreground">
                    {item.input_text}
                  </div>
                  {/* Agent A */}
                  <ResultCell result={item.a} />
                  {/* Agent B */}
                  <ResultCell result={item.b} />
                </div>
              ))}
            </div>
          </div>
        )}

        {test.results.length === 0 && test.status !== "done" && (
          <p className="text-sm text-muted-foreground text-center py-8">
            Results will appear here once the test completes.
          </p>
        )}
      </div>
    </div>
  );
}

function ResultCell({ result }: { result: ItemResult | null }) {
  if (!result) {
    return (
      <div className="px-4 py-3 border-l border-border/30 text-xs text-muted-foreground/50 italic">
        —
      </div>
    );
  }
  const score10 = result.score !== null ? result.score * 10 : null;
  const scoreColor =
    score10 === null
      ? "text-muted-foreground"
      : score10 >= 7
        ? "text-emerald-500"
        : score10 >= 4
          ? "text-amber-500"
          : "text-destructive";

  return (
    <div className="px-4 py-3 border-l border-border/30 space-y-1">
      {score10 !== null && (
        <span className={cn("text-xs font-bold tabular-nums", scoreColor)}>
          {score10.toFixed(1)}/10
        </span>
      )}
      <p className="text-[11px] text-foreground/80 line-clamp-3">{result.actual_output || "—"}</p>
      {result.rationale && (
        <p className="text-[10px] text-muted-foreground line-clamp-2 italic">{result.rationale}</p>
      )}
    </div>
  );
}
