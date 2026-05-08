"use client";

import { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ConfigDiffViewProps {
  changes: Array<{
    key: string;
    old: unknown;
    new: unknown;
  }>;
  oldLabel?: string;
  newLabel?: string;
  className?: string;
}

function formatValue(val: unknown): string {
  if (val === null || val === undefined) return "—";
  if (typeof val === "boolean") return val ? "true" : "false";
  if (typeof val === "object") return JSON.stringify(val, null, 2);
  return String(val);
}

function changeType(old: unknown, new_: unknown): "added" | "removed" | "modified" {
  if (old === undefined || old === null) return "added";
  if (new_ === undefined || new_ === null) return "removed";
  return "modified";
}

export function ConfigDiffView({
  changes,
  oldLabel = "Previous",
  newLabel = "Current",
  className,
}: ConfigDiffViewProps) {
  if (changes.length === 0) {
    return (
      <div className={cn("text-center py-6 text-sm text-muted-foreground", className)}>
        No differences between versions.
      </div>
    );
  }

  return (
    <div className={cn("rounded-xl border border-border/60 bg-card/80 overflow-hidden", className)}>
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border/40 px-4 py-2.5 text-xs">
        <Badge variant="outline" className="font-mono text-[9px] rounded px-1.5 py-0 border-rose-500/30 bg-rose-500/10 text-rose-400">
          {oldLabel}
        </Badge>
        <span className="text-muted-foreground">→</span>
        <Badge variant="outline" className="font-mono text-[9px] rounded px-1.5 py-0 border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
          {newLabel}
        </Badge>
        <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">
          {changes.length} change{changes.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Changes */}
      <div className="divide-y divide-border/30">
        {changes.map((c) => {
          const type = changeType(c.old, c.new);
          return (
            <div key={c.key} className="px-4 py-3">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="font-mono text-xs font-medium text-foreground">{c.key}</span>
                <Badge
                  variant="outline"
                  className={cn(
                    "text-[8px] rounded px-1 py-0 h-3.5",
                    type === "added" && "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
                    type === "removed" && "border-rose-500/30 bg-rose-500/10 text-rose-400",
                    type === "modified" && "border-amber-500/30 bg-amber-500/10 text-amber-400",
                  )}
                >
                  {type}
                </Badge>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {type !== "added" && (
                  <pre className="rounded-md bg-rose-500/5 border border-rose-500/10 p-2 font-mono text-[10px] text-rose-300/80 whitespace-pre-wrap break-all max-h-32 overflow-y-auto">
                    {formatValue(c.old)}
                  </pre>
                )}
                {type === "added" && <div />}
                {type !== "removed" && (
                  <pre className="rounded-md bg-emerald-500/5 border border-emerald-500/10 p-2 font-mono text-[10px] text-emerald-300/80 whitespace-pre-wrap break-all max-h-32 overflow-y-auto">
                    {formatValue(c.new)}
                  </pre>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
