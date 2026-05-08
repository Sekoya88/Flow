"use client";

import { useState } from "react";
import {
  ChevronRight,
  FileText,
  Layers,
  PanelRightClose,
  PanelRightOpen,
  Wrench,
} from "lucide-react";
import { FlowGraph } from "@/components/flow/FlowGraph";
import { ToolCallLog, type ToolCall } from "@/components/flow/ToolCallLog";
import { CitationsPanel } from "@/components/flow/CitationsPanel";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface RunInspectorProps {
  toolCalls: ToolCall[];
  citations: Array<{
    source_id: string;
    title: string;
    chunk_index: number;
    preview: string;
  }>;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function RunInspector({ toolCalls, citations, className }: RunInspectorProps) {
  const [tab, setTab] = useState<"pipeline" | "tools" | "sources">("pipeline");
  const [collapsed, setCollapsed] = useState(false);
  const isRunning = useStore((s) => s.activeExecutionId !== null);
  const nodes = useStore((s) => s.nodes);

  const activeNodeName = Object.entries(nodes).find(
    ([, v]) => v.status === "streaming" || v.status === "thinking",
  )?.[0];

  if (collapsed) {
    return (
      <div className={cn("flex flex-col items-center", className)}>
        <button
          onClick={() => setCollapsed(false)}
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-border/60 bg-card/80 backdrop-blur-sm text-muted-foreground hover:text-foreground transition-colors"
          title="Open inspector"
        >
          <PanelRightOpen className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex w-[380px] shrink-0 flex-col overflow-hidden",
        "rounded-2xl border border-border/60 bg-card/60 backdrop-blur-xl",
        "shadow-lg animate-slide-up",
        className,
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border/40 px-4 py-3">
        <Layers className="h-3.5 w-3.5 text-flow-brand" aria-hidden />
        <span className="flex-1 text-xs font-semibold text-foreground/80">
          Inspector
        </span>
        {isRunning && activeNodeName && (
          <Badge
            variant="outline"
            className="h-5 rounded-full border-flow-streaming/30 bg-flow-streaming/10 px-2 py-0 text-[10px]"
          >
            <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-flow-streaming animate-pulse" />
            {activeNodeName}
          </Badge>
        )}
        <button
          onClick={() => setCollapsed(true)}
          className="rounded-md p-1 text-muted-foreground hover:text-foreground transition-colors"
          title="Collapse inspector"
        >
          <PanelRightClose className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-border/40">
        {(
          [
            { key: "pipeline" as const, label: "Pipeline", icon: Layers, count: undefined as number | undefined },
            { key: "tools" as const, label: "Tools", icon: Wrench, count: toolCalls.length },
            { key: "sources" as const, label: "Sources", icon: FileText, count: citations.length },
          ]
        ).map(({ key, label, icon: Icon, count }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 py-2.5 text-[11px] font-medium transition-colors",
              tab === key
                ? "text-foreground border-b-2 border-flow-brand"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon className="h-3 w-3" />
            {label}
            {count !== undefined && count > 0 && (
              <span className="rounded-full bg-muted px-1.5 py-0 text-[9px] tabular-nums">
                {count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <ScrollArea className="flex-1">
        <div className="p-4">
          {tab === "pipeline" && (
            <div className="space-y-4">
              <FlowGraph className="mx-auto w-full max-w-[340px]" />
              <div className="space-y-2">
                {["planner", "worker", "synthesizer", "reflector"].map((name) => {
                  const node = nodes[name];
                  const status = node?.status ?? "idle";
                  return (
                    <div
                      key={name}
                      className={cn(
                        "flex items-center gap-3 rounded-lg px-3 py-2 text-xs transition-colors",
                        status === "streaming" || status === "thinking"
                          ? "bg-flow-streaming/10 border border-flow-streaming/20"
                          : status === "done"
                            ? "bg-flow-done/5 border border-flow-done/10"
                            : status === "error"
                              ? "bg-flow-error/10 border border-flow-error/20"
                              : "border border-transparent",
                      )}
                    >
                      <span
                        className={cn(
                          "h-2 w-2 rounded-full shrink-0",
                          status === "streaming" || status === "thinking"
                            ? "bg-flow-streaming animate-pulse"
                            : status === "done"
                              ? "bg-flow-done"
                              : status === "error"
                                ? "bg-flow-error"
                                : "bg-muted",
                        )}
                      />
                      <span
                        className={cn(
                          "font-medium capitalize",
                          status === "idle"
                            ? "text-muted-foreground"
                            : "text-foreground",
                        )}
                      >
                        {name}
                      </span>
                      <span className="ml-auto text-[10px] text-muted-foreground capitalize">
                        {status}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {tab === "tools" && (
            <div>
              {toolCalls.length === 0 ? (
                <div className="flex flex-col items-center gap-2 py-8 text-center">
                  <Wrench className="h-6 w-6 text-muted-foreground/30" />
                  <p className="text-xs text-muted-foreground">
                    Tool calls will appear here during execution.
                  </p>
                </div>
              ) : (
                <ToolCallLog calls={toolCalls} />
              )}
            </div>
          )}

          {tab === "sources" && (
            <div>
              {citations.length === 0 ? (
                <div className="flex flex-col items-center gap-2 py-8 text-center">
                  <FileText className="h-6 w-6 text-muted-foreground/30" />
                  <p className="text-xs text-muted-foreground">
                    Citations from knowledge retrieval will appear here.
                  </p>
                </div>
              ) : (
                <CitationsPanel citations={citations} />
              )}
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
