"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Expand, Maximize2, Minimize2, Network, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { KnowledgeGraphCanvas, type KGEdge, type KGNode } from "@/components/kg/KnowledgeGraphCanvas";
import { GraphQueryPanel } from "@/components/kg/GraphQueryPanel";
import { apiFetch } from "@/lib/api";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const NODE_TYPES = ["trace", "skill", "tool_call", "metacog", "note", "concept", "topic", "query", "prompt"] as const;

const TYPE_DOT_COLORS: Record<string, string> = {
  concept: "#94a3b8",
  skill: "#5eead4",
  tool_call: "#fbbf24",
  trace: "#38bdf8",
  metacog: "#a78bfa",
  prompt: "#818cf8",
  note: "#8b9cb7",
  topic: "#67e8f9",
  query: "#7dd3fc",
};

export default function GraphPage() {
  const storeWs = useStore((s) => s.workspaces);
  const [bootedWsId, setBootedWsId] = useState<string | null>(null);
  const workspaceId = storeWs[0]?.id ?? bootedWsId;

  useEffect(() => {
    if (storeWs.length > 0) return;
    apiFetch<{ workspaces: { id: string }[] }>("/api/v1/auth/me")
      .then((m) => { if (m.workspaces[0]) setBootedWsId(m.workspaces[0].id); })
      .catch(() => {});
  }, [storeWs.length]);

  const [nodes, setNodes] = useState<KGNode[]>([]);
  const [edges, setEdges] = useState<KGEdge[]>([]);
  const [loading, setLoading] = useState(true);
  const [highlightedIds, setHighlightedIds] = useState<Set<string>>(new Set());
  const [pathLabels, setPathLabels] = useState<string[]>([]);
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set(NODE_TYPES));
  const [panelOpen, setPanelOpen] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);

  const typesKey = useMemo(() => Array.from(activeTypes).sort().join(","), [activeTypes]);

  const fetchGraph = useCallback(() => {
    if (!workspaceId) return;
    setLoading(true);
    const typesParam = Array.from(activeTypes).join(",");
    apiFetch<{ nodes: KGNode[]; edges: KGEdge[]; cluster_count: number }>(
      `/api/v1/kg/graph?workspace_id=${workspaceId}&node_types=${typesParam}`,
    )
      .then((data) => {
        setNodes(data.nodes ?? []);
        setEdges(data.edges ?? []);
      })
      .catch(console.warn)
      .finally(() => setLoading(false));
  }, [workspaceId, activeTypes]);

  useEffect(() => { fetchGraph(); }, [fetchGraph, typesKey]);

  const seedGraph = useCallback(async () => {
    if (!workspaceId || seeding) return;
    setSeeding(true);
    try {
      await apiFetch(`/api/v1/kg/seed?workspace_id=${workspaceId}`, { method: "POST" });
      fetchGraph();
    } catch (e) {
      console.warn("seed failed", e);
    } finally {
      setSeeding(false);
    }
  }, [workspaceId, seeding, fetchGraph]);

  const toggleType = useCallback((t: string) => {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      next.has(t) ? next.delete(t) : next.add(t);
      return next;
    });
  }, []);

  // Type counts
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const n of nodes) {
      counts[n.node_type] = (counts[n.node_type] || 0) + 1;
    }
    return counts;
  }, [nodes]);

  if (!workspaceId) {
    return (
      <div className="flex h-[calc(100vh-48px)] items-center justify-center">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-flow-brand border-t-transparent" />
      </div>
    );
  }

  return (
    <div className={cn(
      "relative flex overflow-hidden",
      fullscreen ? "fixed inset-0 z-50 bg-background" : "h-[calc(100vh-48px)] p-4 sm:p-6",
    )}>
      {/* Holographic Container */}
      <div className={cn(
        "relative flex flex-1 overflow-hidden",
        !fullscreen && "surface-glass-heavy rounded-3xl shadow-2xl border border-border/50"
      )}>
        {/* Graph canvas */}
      {loading ? (
        <div className="flex flex-1 items-center justify-center">
          <div className="flex flex-col items-center gap-3 animate-fade-in">
            <div className="relative">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-flow-brand border-t-transparent" />
              <div className="absolute inset-0 animate-ping rounded-full border border-flow-brand/20" />
            </div>
            <span className="text-xs text-muted-foreground">Loading graph…</span>
          </div>
        </div>
      ) : nodes.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-6">
          <div className="rounded-2xl border border-border/40 bg-card/60 backdrop-blur-sm p-10 flex flex-col items-center gap-5 max-w-sm animate-fade-in">
            <div className="relative">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-flow-brand/10 border border-flow-brand/20">
                <Network className="h-8 w-8 text-flow-brand/50" />
              </div>
              <div className="absolute -right-1 -bottom-1 flex h-6 w-6 items-center justify-center rounded-full bg-flow-brand border-2 border-background">
                <Sparkles className="h-3 w-3 text-white" />
              </div>
            </div>
            <div className="text-center space-y-2">
              <p className="text-base font-semibold text-foreground">Knowledge Graph</p>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Nodes grow as you run queries, import notes, or connect Obsidian. Seed a demo to preview.
              </p>
            </div>
            <Button
              onClick={() => void seedGraph()}
              disabled={seeding}
              variant="outline"
              size="sm"
              className="gap-2 w-full"
            >
              <Sparkles className="h-3.5 w-3.5" />
              {seeding ? "Seeding…" : "Seed demo graph"}
            </Button>
          </div>
        </div>
      ) : (
        <KnowledgeGraphCanvas
          nodes={nodes}
          edges={edges}
          highlightedNodeIds={highlightedIds}
          highlightedPath={pathLabels}
          className="flex-1 h-full w-full"
        />
      )}

      {/* Floating controls — top left */}
      <div className="absolute top-4 left-4 z-20 flex flex-col gap-3 animate-fade-in">
        {/* Stats bar */}
        {nodes.length > 0 && (
          <div className="rounded-xl border border-border/40 bg-card/85 backdrop-blur-xl p-3 shadow-lg shadow-black/10 space-y-2.5">
            {/* Node/edge counts */}
            <div className="flex items-center gap-3 px-1">
              <Badge variant="outline" className="h-5 rounded-md px-2 py-0 text-[10px] font-mono tabular-nums border-flow-brand/30 bg-flow-brand/10">
                {nodes.length} nodes
              </Badge>
              <Badge variant="outline" className="h-5 rounded-md px-2 py-0 text-[10px] font-mono tabular-nums">
                {edges.length} edges
              </Badge>
            </div>

            {/* Filter chips */}
            <div className="flex flex-wrap gap-1">
              {NODE_TYPES.map((t) => {
                const active = activeTypes.has(t);
                const count = typeCounts[t] || 0;
                return (
                  <button
                    key={t}
                    onClick={() => toggleType(t)}
                    className={cn(
                      "flex items-center gap-1.5 rounded-lg px-2 py-1 text-[10px] font-medium transition-all",
                      active
                        ? "bg-card text-foreground shadow-sm border border-border/60"
                        : "text-muted-foreground/40 hover:text-muted-foreground border border-transparent",
                    )}
                  >
                    <span
                      className="h-2 w-2 rounded-full shrink-0 transition-all"
                      style={{
                        backgroundColor: active ? TYPE_DOT_COLORS[t] : "transparent",
                        border: active ? "none" : `1px solid ${TYPE_DOT_COLORS[t]}60`,
                        boxShadow: active ? `0 0 6px ${TYPE_DOT_COLORS[t]}40` : "none",
                      }}
                    />
                    {t.replace("_", " ")}
                    {count > 0 && active && (
                      <span className="text-[9px] text-muted-foreground tabular-nums">
                        {count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-1.5">
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-[11px] bg-card/85 backdrop-blur-xl border-border/50 shadow-sm"
            onClick={() => setPanelOpen(!panelOpen)}
          >
            {panelOpen ? "Hide panel" : "Query & Import"}
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8 bg-card/85 backdrop-blur-xl border-border/50 shadow-sm"
            onClick={() => setFullscreen(!fullscreen)}
            title={fullscreen ? "Exit fullscreen" : "Fullscreen"}
          >
            {fullscreen ? (
              <Minimize2 className="h-3.5 w-3.5" />
            ) : (
              <Maximize2 className="h-3.5 w-3.5" />
            )}
          </Button>
        </div>
      </div>

      {/* Query/Import panel */}
      {panelOpen && workspaceId && (
        <div className="absolute top-0 right-0 h-full z-30 shadow-2xl animate-slide-up border-l border-border/40 bg-background/50 backdrop-blur-2xl">
          <GraphQueryPanel
            workspaceId={workspaceId}
            onHighlight={(ids) => setHighlightedIds(new Set(ids))}
            onPathHighlight={setPathLabels}
          />
        </div>
      )}
      </div>
    </div>
  );
}
