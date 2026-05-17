"use client";

import { useState, useRef, useEffect } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ChevronDown, ChevronRight, Clock, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface ToolCall {
  id: string;
  tool: string;
  input: Record<string, unknown>;
  output: string;
  duration_ms: number;
  status: "success" | "error";
}

const TOOL_COLORS: Record<string, string> = {
  knowledge_search: "border-blue-500/40 bg-blue-500/10 text-blue-400",
  long_term_memory: "border-purple-500/40 bg-purple-500/10 text-purple-400",
  sandbox: "border-amber-500/40 bg-amber-500/10 text-amber-400",
  tavily_search: "border-green-500/40 bg-green-500/10 text-green-400",
  fetch_webpage: "border-cyan-500/40 bg-cyan-500/10 text-cyan-400",
  arxiv_search: "border-indigo-500/40 bg-indigo-500/10 text-indigo-400",
  hf_papers: "border-orange-500/40 bg-orange-500/10 text-orange-400",
};

function ToolCallRow({ call }: { call: ToolCall }) {
  const [open, setOpen] = useState(false);
  const color = TOOL_COLORS[call.tool] ?? "border-flow-800 bg-muted/20 text-muted-foreground";

  return (
    <div 
      className="overflow-hidden rounded-lg border border-flow-800"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-muted/30"
      >
        {open ? (
          <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
        )}
        <Badge variant="outline" className={cn("h-5 rounded px-1.5 py-0 font-mono text-[10px]", color)}>
          {call.tool}
        </Badge>
        {call.status === "error" && (
          <span className="text-[10px] text-destructive">error</span>
        )}
        <span className="ml-auto flex items-center gap-1 text-[10px] tabular-nums text-muted-foreground">
          <Clock className="h-2.5 w-2.5" aria-hidden />
          {call.duration_ms}ms
        </span>
      </button>

      {open && (
        <div className="space-y-2 border-t border-flow-800 px-3 py-2">
          <div>
            <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Input</p>
            <pre className="max-h-32 overflow-y-auto whitespace-pre-wrap break-words rounded bg-muted/30 p-2 text-[11px] text-foreground/80">
              {JSON.stringify(call.input, null, 2)}
            </pre>
          </div>
          <div>
            <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Output</p>
            <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap break-words rounded bg-muted/30 p-2 text-[11px] text-foreground/80">
              {call.output}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

interface ToolCallLogProps {
  calls: ToolCall[];
  className?: string;
}

export function ToolCallLog({ calls, className }: ToolCallLogProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: calls.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 42, // Closed height estimate
    overscan: 5,
  });

  if (calls.length === 0) return null;

  return (
    <div className={cn("space-y-2 flex flex-col h-full", className)}>
      <div className="flex shrink-0 items-center gap-2">
        <Zap className="h-3.5 w-3.5 text-flow-amber" aria-hidden />
        <span className="text-xs font-medium text-foreground">Tool calls</span>
        <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] tabular-nums text-muted-foreground">
          {calls.length}
        </span>
      </div>
      
      <div 
        ref={parentRef} 
        className="flex-1 overflow-y-auto max-h-[500px]"
      >
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: "100%",
            position: "relative",
          }}
        >
          {virtualizer.getVirtualItems().map((virtualItem) => {
            const c = calls[virtualItem.index];
            return (
              <div
                key={virtualItem.key}
                data-index={virtualItem.index}
                ref={virtualizer.measureElement}
                className="pb-1.5"
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  transform: `translateY(${virtualItem.start}px)`,
                }}
              >
                <ToolCallRow call={c} />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
