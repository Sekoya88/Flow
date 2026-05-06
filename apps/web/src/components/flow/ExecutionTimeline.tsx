"use client";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

export type TraceNode = {
  name: string;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
};

export type TraceToolCall = {
  tool: string;
  duration_ms: number | null;
  status: "success" | "error";
  input: string;
  output: string;
};

export type ExecutionTrace = {
  nodes: TraceNode[];
  tool_calls: TraceToolCall[];
  total_duration_ms: number | null;
  started_at: string | null;
};

const NODE_COLORS: Record<string, string> = {
  planner: "bg-violet-500/80",
  worker: "bg-blue-500/80",
  synthesizer: "bg-emerald-500/80",
  tool_agent: "bg-amber-500/80",
  researcher: "bg-cyan-500/80",
  critic: "bg-orange-500/80",
  writer: "bg-teal-500/80",
};

function fmtMs(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function ExecutionTimeline({ trace }: { trace: ExecutionTrace }) {
  const { nodes, tool_calls, total_duration_ms } = trace;
  const total = total_duration_ms ?? nodes.reduce((s, n) => s + (n.duration_ms ?? 0), 0);

  if (nodes.length === 0) {
    return (
      <p className="text-muted-foreground text-sm italic">No trace data available yet.</p>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Execution timeline</span>
        <Badge variant="secondary" className="font-mono text-xs">
          total {fmtMs(total_duration_ms)}
        </Badge>
      </div>

      {/* Gantt bars */}
      <div className="space-y-2">
        {nodes.map((node, i) => {
          const offset =
            total > 0
              ? (nodes.slice(0, i).reduce((s, n) => s + (n.duration_ms ?? 0), 0) / total) * 100
              : 0;
          const remaining = Math.max(0, 100 - offset);
          const pct =
            total > 0 && node.duration_ms !== null
              ? Math.min(Math.max(4, (node.duration_ms / total) * 100), remaining)
              : Math.min(20, remaining);
          const color = NODE_COLORS[node.name] ?? "bg-slate-500/80";

          return (
            <div key={`${node.name}-${i}`} className="space-y-0.5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span className="font-mono">{node.name}</span>
                <span>{fmtMs(node.duration_ms)}</span>
              </div>
              <div className="relative h-5 w-full overflow-hidden rounded bg-muted/30">
                <div
                  className={cn("absolute inset-y-0 rounded", color)}
                  style={{ left: `${offset}%`, width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Tool calls */}
      {tool_calls.length > 0 && (
        <div className="space-y-1.5 pt-2 border-t border-border/40">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Tool calls ({tool_calls.length})
          </p>
          <div className="space-y-1">
            {tool_calls.map((tc, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-md bg-muted/20 px-2.5 py-1.5 text-xs"
              >
                <span className="font-mono text-foreground/80">{tc.tool}</span>
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">{fmtMs(tc.duration_ms)}</span>
                  <span
                    className={cn(
                      "rounded-full px-1.5 py-0.5 text-[10px] font-medium",
                      tc.status === "success"
                        ? "bg-emerald-500/15 text-emerald-600"
                        : "bg-destructive/15 text-destructive",
                    )}
                  >
                    {tc.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
