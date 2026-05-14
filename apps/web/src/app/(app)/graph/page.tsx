"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { BookOpen, Cpu, GitBranch, Maximize2, Minimize2, Network, Sparkles, X, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { KnowledgeGraphCanvas, type KGEdge, type KGNode } from "@/components/kg/KnowledgeGraphCanvas";
import { GraphQueryPanel } from "@/components/kg/GraphQueryPanel";
import { apiFetch } from "@/lib/api";
import { NODE_COLORS } from "@/lib/graph/graphColors";
import { logger } from "@/lib/logger";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const NODE_TYPES = ["trace", "skill", "tool_call", "metacog", "note", "concept", "topic", "query", "prompt"] as const;

const ENTITY_FILTER_TABS = [
  { type: 'agent',          label: 'Agents',    color: NODE_COLORS.agent },
  { type: 'skill',          label: 'Skills',    color: NODE_COLORS.skill },
  { type: 'genome_version', label: 'Genomes',   color: NODE_COLORS.genome_version },
  { type: 'execution',      label: 'Executions', color: NODE_COLORS.execution },
] as const;

const TYPE_DOT_COLORS: Record<string, string> = {
  concept: "#94a3b8",
  skill: NODE_COLORS.skill,
  tool_call: NODE_COLORS.tool_call,
  trace: "#38bdf8",
  metacog: "#a78bfa",
  prompt: "#818cf8",
  note: "#8b9cb7",
  topic: "#67e8f9",
  query: "#7dd3fc",
  agent: NODE_COLORS.agent,
  genome_version: NODE_COLORS.genome_version,
  execution: NODE_COLORS.execution,
  sub_agent: NODE_COLORS.sub_agent,
  system_prompt: NODE_COLORS.system_prompt,
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
  const [selectedNode, setSelectedNode] = useState<KGNode | null>(null);

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
      .catch((e) => logger.warn("graph fetch failed", { error: String(e) }))
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
      logger.warn("seed failed", { error: String(e) });
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
          onNodeClick={(n) => setSelectedNode((prev) => prev?.id === n.id ? null : n)}
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

            {/* Filter chips — document types */}
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

            {/* Filter chips — entity types */}
            <div className="flex flex-wrap gap-1 pt-1 border-t border-border/30">
              {ENTITY_FILTER_TABS.map(({ type: t, label, color }) => {
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
                        backgroundColor: active ? color : "transparent",
                        border: active ? "none" : `1px solid ${color}60`,
                        boxShadow: active ? `0 0 6px ${color}40` : "none",
                      }}
                    />
                    {label}
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

      {/* Node detail panel */}
      {selectedNode && !panelOpen && (
        <NodeDetailPanel node={selectedNode} onClose={() => setSelectedNode(null)} />
      )}
      {selectedNode && panelOpen && (
        <NodeDetailPanel node={selectedNode} onClose={() => setSelectedNode(null)} offset />
      )}
      </div>
    </div>
  );
}

const NODE_TYPE_ICONS: Record<string, React.ReactNode> = {
  skill: <Zap className="h-3.5 w-3.5" />,
  tool_call: <Cpu className="h-3.5 w-3.5" />,
  trace: <GitBranch className="h-3.5 w-3.5" />,
  prompt: <BookOpen className="h-3.5 w-3.5" />,
};

function NodeDetailPanel({ node, onClose, offset }: { node: KGNode; onClose: () => void; offset?: boolean }) {
  const color = NODE_COLORS[node.node_type as keyof typeof NODE_COLORS] ?? TYPE_DOT_COLORS[node.node_type] ?? "#94a3b8";
  const skills = (node.metadata?.skills as string[] | undefined) ?? [];
  const tools = (node.metadata?.tools as string[] | undefined) ?? [];
  const contentMd = (node.metadata?.content_md ?? node.metadata?.content ?? node.metadata?.body) as string | undefined;
  const sourcePath = node.source_path;
  const metaKeys = Object.keys(node.metadata ?? {}).filter(
    (k) => !["skills", "tools", "content_md", "content", "body"].includes(k),
  );

  return (
    <div
      className={cn(
        "absolute bottom-4 z-40 animate-fade-in",
        offset ? "right-[320px]" : "right-4",
      )}
      style={{ maxWidth: 340, minWidth: 280 }}
    >
      <div className="rounded-2xl border border-border/50 bg-card/95 backdrop-blur-2xl shadow-2xl shadow-black/30 overflow-hidden">
        {/* Header */}
        <div
          className="flex items-start justify-between gap-3 p-4 pb-3"
          style={{ borderBottom: `1px solid ${color}18` }}
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <span
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"
              style={{ backgroundColor: `${color}18`, color }}
            >
              {NODE_TYPE_ICONS[node.node_type] ?? <Network className="h-3.5 w-3.5" />}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground truncate leading-tight">{node.label}</p>
              <span
                className="inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-mono font-medium mt-0.5"
                style={{ backgroundColor: `${color}14`, color, border: `1px solid ${color}28` }}
              >
                {node.node_type.replace("_", " ")}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 rounded-lg p-1 text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="p-4 space-y-3 max-h-72 overflow-y-auto">
          {/* Summary */}
          {node.summary && (
            <p className="text-xs text-muted-foreground leading-relaxed">{node.summary}</p>
          )}

          {/* Content preview */}
          {contentMd && (
            <div className="rounded-lg bg-muted/40 border border-border/40 p-2.5">
              <p className="text-[10px] font-mono text-muted-foreground/60 uppercase tracking-wide mb-1">Content</p>
              <p className="text-xs text-foreground/80 leading-relaxed line-clamp-5 font-mono whitespace-pre-wrap">
                {contentMd.slice(0, 500)}{contentMd.length > 500 ? "…" : ""}
              </p>
            </div>
          )}

          {/* Skills list */}
          {skills.length > 0 && (
            <div>
              <p className="text-[10px] font-mono text-muted-foreground/60 uppercase tracking-wide mb-1.5">Skills</p>
              <div className="flex flex-wrap gap-1">
                {skills.map((s) => (
                  <span
                    key={s}
                    className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium"
                    style={{ backgroundColor: `${TYPE_DOT_COLORS.skill}14`, color: TYPE_DOT_COLORS.skill, border: `1px solid ${TYPE_DOT_COLORS.skill}28` }}
                  >
                    <Zap className="h-2.5 w-2.5" />
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Tools list */}
          {tools.length > 0 && (
            <div>
              <p className="text-[10px] font-mono text-muted-foreground/60 uppercase tracking-wide mb-1.5">Tools</p>
              <div className="flex flex-wrap gap-1">
                {tools.map((t) => (
                  <span
                    key={t}
                    className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium"
                    style={{ backgroundColor: `${TYPE_DOT_COLORS.tool_call}14`, color: TYPE_DOT_COLORS.tool_call, border: `1px solid ${TYPE_DOT_COLORS.tool_call}28` }}
                  >
                    <Cpu className="h-2.5 w-2.5" />
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Source path */}
          {sourcePath && (
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <BookOpen className="h-3 w-3 shrink-0" />
              <span className="truncate font-mono">{sourcePath}</span>
            </div>
          )}

          {/* Pagerank */}
          {node.pagerank > 0 && (
            <div className="flex items-center justify-between text-[10px] text-muted-foreground/60 font-mono pt-1 border-t border-border/30">
              <span>PageRank</span>
              <span className="tabular-nums">{node.pagerank.toFixed(4)}</span>
            </div>
          )}

          {/* Extra metadata keys */}
          {metaKeys.length > 0 && (
            <div className="space-y-1 pt-1 border-t border-border/30">
              {metaKeys.slice(0, 5).map((k) => (
                <div key={k} className="flex items-start gap-2 text-[10px]">
                  <span className="text-muted-foreground/50 font-mono shrink-0 pt-px">{k}</span>
                  <span className="text-muted-foreground/80 font-mono truncate">
                    {String(node.metadata[k]).slice(0, 60)}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Entity-specific sections */}
          {node.node_type === 'agent' && (
            <div className="mt-3 space-y-2">
              <p className="text-xs text-slate-500 uppercase tracking-wide">Template</p>
              <p className="text-sm text-slate-300">
                {String(node.metadata?.template ?? '—')}
              </p>
              <p className="text-xs text-slate-500 uppercase tracking-wide mt-2">Status</p>
              <p className="text-sm text-slate-300">
                {String(node.metadata?.status ?? '—')}
              </p>
              {node.ref_id && (
                <a
                  href={`/agents/${node.ref_id}`}
                  className="mt-3 block w-full text-center bg-indigo-600 hover:bg-indigo-500 text-white text-xs py-1.5 rounded"
                >
                  Open agent page ↗
                </a>
              )}
            </div>
          )}

          {node.node_type === 'genome_version' && (
            <div className="mt-3 space-y-2">
              <p className="text-xs text-slate-500 uppercase tracking-wide">Model</p>
              <p className="text-sm text-slate-300">
                {String(node.metadata?.provider ?? '')} / {String(node.metadata?.model ?? '—')}
              </p>
              <p className="text-xs text-slate-500 uppercase tracking-wide mt-2">Status</p>
              <span className={`text-xs px-2 py-0.5 rounded ${
                node.metadata?.status === 'active'
                  ? 'bg-amber-900/40 text-amber-400'
                  : 'bg-slate-700 text-slate-400'
              }`}>
                {String(node.metadata?.status ?? '—')}
                {node.metadata?.status === 'active' && ' ✦'}
              </span>
            </div>
          )}

          {node.node_type === 'skill' && (
            <div className="mt-3 space-y-2">
              <p className="text-xs text-slate-500 uppercase tracking-wide">Version</p>
              <p className="text-sm text-slate-300">v{String(node.metadata?.version ?? '—')}</p>
              <p className="text-xs text-slate-500 uppercase tracking-wide mt-2">Score</p>
              <p className="text-sm text-slate-300">{String(node.metadata?.score ?? '—')}</p>
            </div>
          )}

          {node.node_type === 'execution' && (
            <div className="mt-3 space-y-2">
              <p className="text-xs text-slate-500 uppercase tracking-wide">Status</p>
              <span className={`text-xs px-2 py-0.5 rounded ${
                node.metadata?.status === 'completed'
                  ? 'bg-emerald-900/40 text-emerald-400'
                  : 'bg-red-900/40 text-red-400'
              }`}>
                {String(node.metadata?.status ?? '—')}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
