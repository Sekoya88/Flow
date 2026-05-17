"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { BookOpen, Cpu, GitBranch, Maximize2, Minimize2, Network, RefreshCw, Sparkles, X, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { KnowledgeGraphCanvas, type KGEdge, type KGNode } from "@/components/kg/KnowledgeGraphCanvas";
import { GraphQueryPanel } from "@/components/kg/GraphQueryPanel";
import { GraphControls } from "@/components/kg/GraphControls";
import { GraphSearchOverlay } from "@/components/kg/GraphSearchOverlay";
import { apiFetch } from "@/lib/api";
import { NODE_COLORS } from "@/lib/graph/graphColors";
import { logger } from "@/lib/logger";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";

interface SkillNodeDetail {
  content_md: string | null;
  description: string | null;
  allowed_tools: string[];
  triggers: string[];
  score: number;
  use_count: number;
  version: number;
}

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
  const router = useRouter();
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
  const [panelOpen, setPanelOpen] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [selectedNode, setSelectedNode] = useState<KGNode | null>(null);

  // Quartz-style controls
  const [depth, setDepth] = useState<number>(0);  // 0 = unlimited
  const [localMode, setLocalMode] = useState<boolean>(false);
  const [searchOpen, setSearchOpen] = useState<boolean>(false);
  const [skillDetail, setSkillDetail] = useState<SkillNodeDetail | null>(null);
  const [visitedIds, setVisitedIds] = useState<Set<string>>(() => {
    if (typeof window === "undefined") return new Set();
    try {
      const raw = window.localStorage.getItem("flow_graph_visited");
      return raw ? new Set(JSON.parse(raw) as string[]) : new Set();
    } catch {
      return new Set();
    }
  });

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

  const syncEntities = useCallback(async () => {
    if (!workspaceId || syncing) return;
    setSyncing(true);
    try {
      await apiFetch(`/api/v1/kg/sync-entities?workspace_id=${workspaceId}`, { method: "POST" });
      fetchGraph();
    } catch (e) {
      logger.warn("sync-entities failed", { error: String(e) });
    } finally {
      setSyncing(false);
    }
  }, [workspaceId, syncing, fetchGraph]);

  // Auto-sync agents+skills into graph on first load
  const syncedRef = React.useRef(false);
  useEffect(() => {
    if (!workspaceId || syncedRef.current) return;
    syncedRef.current = true;
    void syncEntities();
  }, [workspaceId, syncEntities]);

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

  // Type counts (raw, pre-filter)
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const n of nodes) {
      counts[n.node_type] = (counts[n.node_type] || 0) + 1;
    }
    return counts;
  }, [nodes]);

  // BFS depth + local-mode filter. Active only when a focus node is selected.
  const filteredView = useMemo(() => {
    const hasFocus = selectedNode != null;
    const shouldFilter = hasFocus && (depth > 0 || localMode);
    if (!shouldFilter) return { nodes, edges };

    const adjacency = new Map<string, string[]>();
    for (const e of edges) {
      const a = e.source_id;
      const b = e.target_id;
      if (!adjacency.has(a)) adjacency.set(a, []);
      if (!adjacency.has(b)) adjacency.set(b, []);
      adjacency.get(a)!.push(b);
      adjacency.get(b)!.push(a);
    }

    const reachable = new Set<string>();
    const focusId = selectedNode!.id;
    reachable.add(focusId);
    const maxHops = depth === 0 ? Number.POSITIVE_INFINITY : depth;
    let frontier: string[] = [focusId];
    let hops = 0;
    while (frontier.length > 0 && hops < maxHops) {
      const nextFrontier: string[] = [];
      for (const id of frontier) {
        for (const nb of adjacency.get(id) ?? []) {
          if (!reachable.has(nb)) {
            reachable.add(nb);
            nextFrontier.push(nb);
          }
        }
      }
      frontier = nextFrontier;
      hops += 1;
    }

    const filteredNodes = nodes.filter((n) => reachable.has(n.id));
    const filteredEdges = edges.filter(
      (e) => reachable.has(e.source_id) && reachable.has(e.target_id),
    );
    return { nodes: filteredNodes, edges: filteredEdges };
  }, [nodes, edges, depth, localMode, selectedNode]);

  const displayNodes = filteredView.nodes;
  const displayEdges = filteredView.edges;

  // Cmd+G / Ctrl+G shortcut for graph search overlay (browser hijacks Cmd+F; G is free).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "g") {
        e.preventDefault();
        setSearchOpen((v) => !v);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  // Fetch enriched skill detail when a skill node is selected.
  useEffect(() => {
    setSkillDetail(null);
    if (!selectedNode || !workspaceId) return;
    if (selectedNode.node_type !== "skill") return;
    apiFetch<{ skill: SkillNodeDetail | null }>(
      `/api/v1/kg/graph/node/${selectedNode.id}?workspace_id=${workspaceId}`,
    )
      .then((r) => {
        if (r.skill) setSkillDetail(r.skill);
      })
      .catch(() => {});
  }, [selectedNode, workspaceId]);

  // Track visited nodes in localStorage.
  const markVisited = useCallback((nodeId: string) => {
    setVisitedIds((prev) => {
      if (prev.has(nodeId)) return prev;
      const next = new Set(prev);
      next.add(nodeId);
      try {
        window.localStorage.setItem(
          "flow_graph_visited",
          JSON.stringify(Array.from(next)),
        );
      } catch {
        /* ignore quota */
      }
      return next;
    });
  }, []);

  const handleNodeClick = useCallback(
    (n: KGNode) => {
      markVisited(n.id);
      setSelectedNode((prev) => (prev?.id === n.id ? null : n));
    },
    [markVisited],
  );

  const handleSearchSelect = useCallback(
    (nodeId: string) => {
      const node = nodes.find((x) => x.id === nodeId);
      if (node) {
        markVisited(node.id);
        setSelectedNode(node);
      }
    },
    [nodes, markVisited],
  );

  if (!workspaceId) {
    return (
      <div className="flex h-[calc(100vh-48px)] items-center justify-center">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-flow-amber border-t-transparent" />
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
        !fullscreen && "flow-card rounded-[6px] border border-flow-800"
      )}>
        {/* Graph canvas */}
      {loading ? (
        <div className="flex flex-1 items-center justify-center">
          <div className="flex flex-col items-center gap-3 animate-fade-in">
            <div className="relative">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-flow-amber border-t-transparent" />
              <div className="absolute inset-0 animate-ping rounded-full border border-flow-amber/20" />
            </div>
            <span className="text-xs text-muted-foreground">Loading graph…</span>
          </div>
        </div>
      ) : nodes.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-6">
          <div className="rounded-[6px] border border-flow-800 bg-card p-10 flex flex-col items-center gap-5 max-w-sm animate-fade-in">
            <div className="relative">
              <div className="flex h-16 w-16 items-center justify-center rounded-[6px] bg-flow-amber/10 border border-flow-amber/20">
                <Network className="h-8 w-8 text-flow-amber/50" />
              </div>
              <div className="absolute -right-1 -bottom-1 flex h-6 w-6 items-center justify-center rounded-full bg-flow-amber border-2 border-background">
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
          nodes={displayNodes}
          edges={displayEdges}
          highlightedNodeIds={highlightedIds}
          highlightedPath={pathLabels}
          className="flex-1 h-full w-full"
          onNodeClick={handleNodeClick}
        />
      )}

      {/* Floating controls — top left */}
      <div className="absolute top-4 left-4 z-20 flex flex-col gap-3 animate-fade-in">
        {/* Stats bar */}
        {nodes.length > 0 && (
          <div className="rounded-xl border border-flow-800 bg-card p-3 shadow-black/10 space-y-2.5">
            {/* Node/edge counts */}
            <div className="flex items-center gap-3 px-1">
              <Badge variant="outline" className="h-5 rounded-md px-2 py-0 text-[10px] font-mono tabular-nums border-flow-amber/30 bg-flow-amber/10">
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
                        ? "bg-card text-foreground border border-flow-800"
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
                        ? "bg-card text-foreground border border-flow-800"
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

        {/* Quartz-style graph controls */}
        <GraphControls
          depth={depth}
          setDepth={setDepth}
          localMode={localMode}
          setLocalMode={setLocalMode}
          hasFocus={selectedNode != null}
          onOpenSearch={() => setSearchOpen(true)}
        />

        {/* Action buttons */}
        <div className="flex gap-1.5">
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8 bg-card border-flow-800"
            onClick={() => void syncEntities()}
            disabled={syncing}
            title="Sync skills into graph"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", syncing && "animate-spin")} />
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-[11px] bg-card border-flow-800"
            onClick={() => setPanelOpen(!panelOpen)}
          >
            {panelOpen ? "Hide panel" : "Query & Import"}
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8 bg-card border-flow-800"
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
        <div className="absolute top-0 right-0 h-full z-30 animate-slide-up border-l border-flow-800 bg-flow-950">
          <GraphQueryPanel
            workspaceId={workspaceId}
            onHighlight={(ids) => setHighlightedIds(new Set(ids))}
            onPathHighlight={setPathLabels}
          />
        </div>
      )}

      {/* Node detail panel */}
      {selectedNode && !panelOpen && (
        <NodeDetailPanel
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
          skill={skillDetail}
          onNavigate={(href) => router.push(href)}
        />
      )}
      {selectedNode && panelOpen && (
        <NodeDetailPanel
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
          offset
          skill={skillDetail}
          onNavigate={(href) => router.push(href)}
        />
      )}

      {/* Cmd+G search overlay */}
      <GraphSearchOverlay
        open={searchOpen}
        onOpenChange={setSearchOpen}
        nodes={nodes.map((n) => ({
          id: n.id,
          label: n.label,
          node_type: n.node_type,
          summary: n.summary,
        }))}
        onSelect={handleSearchSelect}
      />
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

function NodeDetailPanel({
  node,
  onClose,
  offset,
  skill,
  onNavigate,
}: {
  node: KGNode;
  onClose: () => void;
  offset?: boolean;
  skill?: SkillNodeDetail | null;
  onNavigate?: (href: string) => void;
}) {
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
      <div className="rounded-[6px] border border-flow-800 bg-card/95 shadow-black/30 overflow-hidden">
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
            <div className="rounded-lg bg-muted/40 border border-flow-800 p-2.5">
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
            <div className="mt-3 space-y-3 border-t border-border/30 pt-3">
              {skill?.description && (
                <p className="text-xs italic text-foreground/70 leading-relaxed">
                  {skill.description}
                </p>
              )}
              {skill?.content_md && (
                <div className="rounded-lg bg-muted/30 border border-flow-800 p-2.5 max-h-44 overflow-y-auto">
                  <p className="text-[10px] font-mono text-flow-amber/80 uppercase tracking-wide mb-1.5">
                    SKILL.md
                  </p>
                  <pre className="text-[11px] text-foreground/85 leading-relaxed font-mono whitespace-pre-wrap">
                    {skill.content_md.slice(0, 1500)}
                    {skill.content_md.length > 1500 ? "…" : ""}
                  </pre>
                </div>
              )}
              {skill && skill.allowed_tools.length > 0 && (
                <div>
                  <p className="text-[10px] font-mono text-muted-foreground/60 uppercase tracking-wide mb-1.5">
                    Allowed tools
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {skill.allowed_tools.map((t) => (
                      <span
                        key={t}
                        className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium"
                        style={{
                          backgroundColor: `${TYPE_DOT_COLORS.tool_call}14`,
                          color: TYPE_DOT_COLORS.tool_call,
                          border: `1px solid ${TYPE_DOT_COLORS.tool_call}28`,
                        }}
                      >
                        <Cpu className="h-2.5 w-2.5" />
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {skill && skill.triggers.length > 0 && (
                <div>
                  <p className="text-[10px] font-mono text-muted-foreground/60 uppercase tracking-wide mb-1.5">
                    Triggers
                  </p>
                  <ul className="space-y-0.5">
                    {skill.triggers.map((t) => (
                      <li
                        key={t}
                        className="text-[11px] italic text-muted-foreground/80 before:mr-1 before:content-['›']"
                      >
                        {t}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="flex items-center gap-3 pt-1 text-[10px] font-mono text-muted-foreground/60">
                <span>v{String(skill?.version ?? node.metadata?.version ?? "—")}</span>
                <span className="text-muted-foreground/30">·</span>
                <span>score {(skill?.score ?? Number(node.metadata?.score ?? 0)).toFixed(2)}</span>
                <span className="text-muted-foreground/30">·</span>
                <span>{skill?.use_count ?? 0} uses</span>
              </div>
              {skill && skill.score > 0 && (
                <div className="h-1 w-full overflow-hidden rounded-full bg-muted/40">
                  <div
                    className="h-full rounded-full bg-flow-amber transition-all duration-500"
                    style={{ width: `${Math.min(100, skill.score * 100)}%` }}
                  />
                </div>
              )}
              {node.ref_id && onNavigate && (
                <button
                  onClick={() => onNavigate(`/agents`)}
                  className="mt-2 block w-full rounded-lg border border-flow-amber/30 bg-flow-amber/10 px-3 py-1.5 text-center text-xs text-flow-amber hover:bg-flow-amber/15 transition-colors"
                >
                  Manage agents using this skill ↗
                </button>
              )}
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
