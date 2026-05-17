"use client";

import { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface SkillDiffViewProps {
  oldContent: string;
  newContent: string;
  oldLabel?: string;
  newLabel?: string;
  className?: string;
}

type DiffLine = {
  type: "add" | "remove" | "same";
  content: string;
  oldNum?: number;
  newNum?: number;
};

function computeDiff(oldText: string, newText: string): DiffLine[] {
  const oldLines = oldText.split("\n");
  const newLines = newText.split("\n");
  const result: DiffLine[] = [];

  // Simple LCS-based diff
  const m = oldLines.length;
  const n = newLines.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldLines[i - 1] === newLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack
  const lcs: Array<[number, number]> = [];
  let i = m, j = n;
  while (i > 0 && j > 0) {
    if (oldLines[i - 1] === newLines[j - 1]) {
      lcs.unshift([i - 1, j - 1]);
      i--;
      j--;
    } else if (dp[i - 1][j] > dp[i][j - 1]) {
      i--;
    } else {
      j--;
    }
  }

  let oi = 0, ni = 0;
  for (const [lo, ln] of lcs) {
    while (oi < lo) {
      result.push({ type: "remove", content: oldLines[oi], oldNum: oi + 1 });
      oi++;
    }
    while (ni < ln) {
      result.push({ type: "add", content: newLines[ni], newNum: ni + 1 });
      ni++;
    }
    result.push({ type: "same", content: oldLines[lo], oldNum: lo + 1, newNum: ln + 1 });
    oi = lo + 1;
    ni = ln + 1;
  }
  while (oi < m) {
    result.push({ type: "remove", content: oldLines[oi], oldNum: oi + 1 });
    oi++;
  }
  while (ni < n) {
    result.push({ type: "add", content: newLines[ni], newNum: ni + 1 });
    ni++;
  }

  return result;
}

export function SkillDiffView({
  oldContent,
  newContent,
  oldLabel = "Previous",
  newLabel = "Current",
  className,
}: SkillDiffViewProps) {
  const diff = useMemo(() => computeDiff(oldContent, newContent), [oldContent, newContent]);

  const stats = useMemo(() => {
    let added = 0, removed = 0;
    for (const line of diff) {
      if (line.type === "add") added++;
      if (line.type === "remove") removed++;
    }
    return { added, removed };
  }, [diff]);

  return (
    <div className={cn("rounded-[6px] border border-flow-800 bg-card/80 overflow-hidden", className)}>
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-flow-800 px-5 py-3">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-[10px] font-mono rounded px-1.5 py-0 border-rose-500/30 bg-rose-500/10 text-rose-400">
            {oldLabel}
          </Badge>
          <span className="text-muted-foreground text-xs">→</span>
          <Badge variant="outline" className="text-[10px] font-mono rounded px-1.5 py-0 border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
            {newLabel}
          </Badge>
        </div>
        <div className="ml-auto flex items-center gap-2 text-[10px]">
          {stats.added > 0 && (
            <span className="text-emerald-500 font-mono tabular-nums">+{stats.added}</span>
          )}
          {stats.removed > 0 && (
            <span className="text-rose-500 font-mono tabular-nums">−{stats.removed}</span>
          )}
        </div>
      </div>

      {/* Diff lines */}
      <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
        <table className="w-full border-collapse font-mono text-xs">
          <tbody>
            {diff.map((line, idx) => (
              <tr
                key={idx}
                className={cn(
                  line.type === "add" && "bg-emerald-500/8",
                  line.type === "remove" && "bg-rose-500/8",
                )}
              >
                {/* Old line number */}
                <td className="w-10 px-2 py-0 text-right text-[10px] text-muted-foreground/40 select-none tabular-nums border-r border-border/20">
                  {line.type !== "add" ? line.oldNum : ""}
                </td>
                {/* New line number */}
                <td className="w-10 px-2 py-0 text-right text-[10px] text-muted-foreground/40 select-none tabular-nums border-r border-border/20">
                  {line.type !== "remove" ? line.newNum : ""}
                </td>
                {/* Indicator */}
                <td className={cn(
                  "w-5 px-1.5 py-0 text-center select-none",
                  line.type === "add" && "text-emerald-500",
                  line.type === "remove" && "text-rose-500",
                )}>
                  {line.type === "add" ? "+" : line.type === "remove" ? "−" : " "}
                </td>
                {/* Content */}
                <td className="px-3 py-0 whitespace-pre-wrap break-all">
                  <span className={cn(
                    "leading-[1.5rem]",
                    line.type === "add" && "text-emerald-300",
                    line.type === "remove" && "text-rose-300",
                    line.type === "same" && "text-foreground/70",
                  )}>
                    {line.content || "\u00A0"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
