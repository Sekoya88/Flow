"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { NODE_COLORS, NODE_SIZE } from "@/lib/graph/graphColors";
import { cn } from "@/lib/utils";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

export interface KGNode {
  id: string;
  label: string;
  node_type: "note" | "concept" | "topic" | "query" | "trace" | "skill" | "tool_call" | "prompt" | "metacog"
    | "agent" | "genome_version" | "execution" | "sub_agent" | "system_prompt" | "paper";
  ref_id?: string | null;
  summary: string | null;
  source_path: string | null;
  cluster_id: number | null;
  pagerank: number;
  pos_x: number;
  pos_y: number;
  metadata: Record<string, unknown>;
}

export interface KGEdge {
  id: string;
  source_id: string;
  target_id: string;
  edge_type: string;
  weight: number;
}

const TYPE_COLORS: Record<string, string> = {
  concept: "#94a3b8",
  skill: "#5eead4",
  tool_call: "#a78bfa",
  trace: "#38bdf8",
  metacog: "#a78bfa",
  prompt: "#818cf8",
  note: "#8b9cb7",
  topic: "#67e8f9",
  query: "#7dd3fc",
  paper: "#f97316",
};

interface Props {
  nodes: KGNode[];
  edges: KGEdge[];
  highlightedNodeIds?: Set<string>;
  highlightedPath?: string[];
  className?: string;
  onNodeClick?: (node: KGNode) => void;
}

interface GraphNode {
  id: string;
  label: string;
  node_type: string;
  summary: string | null;
  pagerank: number;
  cluster_id: number | null;
  color: string;
  val: number;
  _raw: KGNode;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  edge_type: string;
}

const LABEL_ZOOM_THRESHOLD = 1.4;

function nodeRadius(val: number): number {
  return Math.max(2.6, Math.min((val || 4) * 0.7, 9));
}

export function KnowledgeGraphCanvas({
  nodes,
  edges,
  highlightedNodeIds,
  className,
  onNodeClick,
}: Props) {
  const fgRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [hoveredNode, setHoveredNode] = useState<KGNode | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const fittedRef = useRef(false);

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width: Math.max(width, 200), height: Math.max(height, 200) });
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const graphData = useMemo(() => {
    const gNodes: GraphNode[] = nodes.map((n) => ({
      id: n.id,
      label: n.label,
      node_type: n.node_type,
      summary: n.summary,
      pagerank: n.pagerank,
      cluster_id: n.cluster_id,
      color: NODE_COLORS[n.node_type as keyof typeof NODE_COLORS] ?? TYPE_COLORS[n.node_type] ?? "#8b9cb7",
      val: NODE_SIZE[n.node_type as keyof typeof NODE_SIZE] ?? Math.max(2, n.pagerank * 25 + 3),
      _raw: n,
    }));
    const nodeIds = new Set(gNodes.map((n) => n.id));
    const gLinks: GraphLink[] = edges
      .filter((e) => nodeIds.has(e.source_id) && nodeIds.has(e.target_id))
      .map((e) => ({
        source: e.source_id,
        target: e.target_id,
        edge_type: e.edge_type,
      }));
    return { nodes: gNodes, links: gLinks };
  }, [nodes, edges]);

  // Adjacency map for incident-edge highlighting
  const adjacency = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const link of graphData.links) {
      const a = typeof link.source === "object" ? link.source.id : link.source;
      const b = typeof link.target === "object" ? link.target.id : link.target;
      if (!map.has(a)) map.set(a, new Set());
      if (!map.has(b)) map.set(b, new Set());
      map.get(a)!.add(b);
      map.get(b)!.add(a);
    }
    return map;
  }, [graphData.links]);

  const handleNodeClick = useCallback((node: any) => {
    if (onNodeClick && node._raw) onNodeClick(node._raw);
    if (fgRef.current) {
      fgRef.current.centerAt(node.x ?? 0, node.y ?? 0, 600);
      fgRef.current.zoom(3.2, 600);
    }
  }, [onNodeClick]);

  // Multi-pass auto-fit: physics settles over ~2s, so refit at intervals
  // to catch outliers as they're pulled toward the cluster.
  useEffect(() => {
    fittedRef.current = false;
    if (graphData.nodes.length === 0) return;
    const timers: number[] = [];
    const fit = () => {
      if (fgRef.current) {
        try {
          fgRef.current.zoomToFit(400, 60);
        } catch {
          /* ignore */
        }
      }
    };
    timers.push(window.setTimeout(fit, 400));
    timers.push(window.setTimeout(() => {
      fit();
      fittedRef.current = true; // stop auto-fitting after second pass
    }, 1200));
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [graphData.nodes.length]);

  // Tight physics so the graph clusters around hubs instead of drifting outward.
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg || graphData.nodes.length === 0) return;
    let cancelled = false;
    const apply = () => {
      if (cancelled || !fgRef.current) return;
      try {
        const charge = fg.d3Force?.("charge");
        if (charge?.strength) charge.strength(-420);
        const link = fg.d3Force?.("link");
        if (link?.distance) link.distance(120);
        if (link?.strength) link.strength(0.15);
        const center = fg.d3Force?.("center");
        if (center?.strength) center.strength(0.02);
        // NOTE: do NOT call d3ReheatSimulation — the engine reheats
        // automatically when forces change. Manual reheat keeps the
        // sim permanently hot, which makes drag/click feel laggy.
      } catch {
        /* ignore — defaults still better than nothing */
      }
    };
    // Apply once now; sometimes the force-graph instance binds d3 forces
    // slightly after mount, so re-apply after a tick to be safe.
    apply();
    const t = window.setTimeout(apply, 80);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [graphData.nodes.length]);

  const handleEngineStop = useCallback(() => {
    if (!fittedRef.current && fgRef.current && graphData.nodes.length > 0) {
      fittedRef.current = true;
      try {
        fgRef.current.zoomToFit(400, 80);
      } catch {
        /* ignore */
      }
    }
  }, [graphData.nodes.length]);

  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const isHighlighted = highlightedNodeIds?.has(node.id) ?? false;
      const isHovered = hoveredId === node.id;
      const isIncident =
        hoveredId != null && adjacency.get(hoveredId)?.has(node.id) === true;

      // Dot radius — linear scale on NODE_SIZE so hubs read as hubs
      const baseRadius = nodeRadius(node.val);
      const radius = isHighlighted || isHovered ? baseRadius * 1.45 : baseRadius;

      // Faded vs lit alpha when something is hovered/highlighted elsewhere
      const anyFocus = isHighlighted || isHovered || isIncident || hoveredId == null;
      const alpha = anyFocus ? 0.92 : 0.32;

      // Obsidian-style glow
      ctx.shadowBlur = isHighlighted || isHovered ? 22 : isIncident ? 12 : 7;
      ctx.shadowColor = withAlpha(node.color, isHighlighted || isHovered ? 0.95 : 0.55);

      // Dot fill
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
      ctx.fillStyle = withAlpha(node.color, alpha);
      ctx.fill();

      ctx.shadowBlur = 0;
      ctx.shadowColor = "transparent";

      // Subtle dark ring for separation against the dark background
      ctx.lineWidth = 0.6 / globalScale;
      ctx.strokeStyle = `rgba(15,23,42,${0.65 * alpha})`;
      ctx.stroke();

      // Halo for highlighted / hovered nodes
      if (isHighlighted || isHovered) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius * 2.6, 0, 2 * Math.PI, false);
        ctx.fillStyle = withAlpha(node.color, 0.12);
        ctx.fill();
      }

      // Labels only on zoom or interaction — never unconditionally for hub nodes
      const shouldShowLabel =
        isHighlighted ||
        isHovered ||
        isIncident ||
        globalScale > LABEL_ZOOM_THRESHOLD;

      if (shouldShowLabel) {
        const fontSize = Math.max(9, 11 / Math.sqrt(globalScale));
        ctx.font = `500 ${fontSize}px system-ui, -apple-system, sans-serif`;
        const text = node.label.length > 36 ? node.label.slice(0, 34) + "…" : node.label;
        const labelY = node.y + radius + fontSize + 2;

        // Text shadow for legibility instead of pill background
        ctx.shadowBlur = 5;
        ctx.shadowColor = "rgba(0,0,0,0.95)";
        const baseAlpha = isHighlighted || isHovered ? 1 : 0.82;
        ctx.fillStyle = `rgba(226,232,240,${baseAlpha})`;
        ctx.textAlign = "center";
        ctx.textBaseline = "alphabetic";
        ctx.fillText(text, node.x, labelY);
        ctx.shadowBlur = 0;
        ctx.shadowColor = "transparent";
      }
    },
    [highlightedNodeIds, hoveredId, adjacency],
  );

  // Increase hit area for pointer events so dots stay clickable
  const nodePointerAreaPaint = useCallback(
    (node: any, color: string, ctx: CanvasRenderingContext2D) => {
      const r = nodeRadius(node.val);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(node.x, node.y, r * 2.4, 0, 2 * Math.PI, false);
      ctx.fill();
    },
    [],
  );

  const linkColor = useCallback(
    (link: any) => {
      const sourceId = typeof link.source === "object" ? link.source.id : link.source;
      const targetId = typeof link.target === "object" ? link.target.id : link.target;
      const incidentToHover =
        hoveredId != null && (sourceId === hoveredId || targetId === hoveredId);
      const incidentToHighlight =
        highlightedNodeIds &&
        (highlightedNodeIds.has(sourceId) || highlightedNodeIds.has(targetId));
      if (incidentToHover || incidentToHighlight) {
        return "rgba(94,234,212,0.65)";
      }
      // Faded when something else is in focus
      if (hoveredId != null) return "rgba(148,163,184,0.10)";
      return "rgba(148,163,184,0.28)";
    },
    [hoveredId, highlightedNodeIds],
  );

  const linkWidth = useCallback(
    (link: any) => {
      const sourceId = typeof link.source === "object" ? link.source.id : link.source;
      const targetId = typeof link.target === "object" ? link.target.id : link.target;
      const incident =
        hoveredId != null && (sourceId === hoveredId || targetId === hoveredId);
      const highlighted =
        highlightedNodeIds &&
        (highlightedNodeIds.has(sourceId) || highlightedNodeIds.has(targetId));
      if (incident || highlighted) return 1.6;
      return 0.55;
    },
    [hoveredId, highlightedNodeIds],
  );

  return (
    <div ref={containerRef} className={cn("relative h-full w-full overflow-hidden rounded-[6px]", className)}>
      {graphData.nodes.length > 0 && (
        <ForceGraph2D
          ref={fgRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          nodeCanvasObject={nodeCanvasObject}
          nodeCanvasObjectMode={() => "replace"}
          nodePointerAreaPaint={nodePointerAreaPaint}
          linkColor={linkColor}
          linkWidth={linkWidth}
          linkLineDash={() => null}
          backgroundColor="rgba(0,0,0,0)"
          onNodeClick={handleNodeClick}
          onNodeHover={(node: any) => {
            setHoveredNode(node?._raw ?? null);
            setHoveredId(node?.id ?? null);
          }}
          enableNodeDrag={true}
          enableZoomInteraction={true}
          enablePanInteraction={true}
          warmupTicks={120}
          cooldownTicks={300}
          cooldownTime={4000}
          d3AlphaDecay={0.02}
          d3VelocityDecay={0.4}
          nodeRelSize={2.4}
          onEngineStop={handleEngineStop}
        />
      )}

      {/* Hover card — polished */}
      {hoveredNode && (
        <div className="absolute top-4 left-4 max-w-80 rounded-[6px] border border-flow-800 bg-card/95 p-5 pointer-events-none z-10 shadow-black/20 animate-fade-in">
          <div className="flex items-center gap-3 mb-3">
            <span
              className="h-3 w-3 rounded-full shrink-0 ring-2 ring-offset-2 ring-offset-card"
              style={{
                backgroundColor: TYPE_COLORS[hoveredNode.node_type] ?? "#8b9cb7",
                boxShadow: `0 0 12px ${TYPE_COLORS[hoveredNode.node_type] ?? "#8b9cb7"}50`,
              }}
            />
            <span className="text-sm font-semibold text-foreground truncate">{hoveredNode.label}</span>
          </div>
          <div className="flex items-center gap-2 mb-2">
            <span
              className="inline-flex items-center rounded-lg px-2 py-0.5 text-[10px] font-mono font-medium"
              style={{
                backgroundColor: `${TYPE_COLORS[hoveredNode.node_type] ?? "#8b9cb7"}15`,
                color: TYPE_COLORS[hoveredNode.node_type] ?? "#8b9cb7",
                border: `1px solid ${TYPE_COLORS[hoveredNode.node_type] ?? "#8b9cb7"}30`,
              }}
            >
              {hoveredNode.node_type.replace("_", " ")}
            </span>
            {hoveredNode.pagerank > 0.1 && (
              <span className="text-[10px] text-muted-foreground font-mono tabular-nums">
                PR: {hoveredNode.pagerank.toFixed(2)}
              </span>
            )}
            {hoveredNode.cluster_id !== null && (
              <span className="text-[10px] text-muted-foreground font-mono">
                Cluster {hoveredNode.cluster_id}
              </span>
            )}
          </div>
          {hoveredNode.summary && (
            <p className="text-xs text-muted-foreground leading-relaxed line-clamp-4">
              {hoveredNode.summary}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function withAlpha(hex: string, alpha: number): string {
  // Accept #rrggbb / rgba()/ rgb(). Best-effort fallback.
  if (hex.startsWith("rgba")) return hex;
  if (hex.startsWith("rgb(")) {
    return hex.replace("rgb(", "rgba(").replace(")", `,${alpha})`);
  }
  if (hex.startsWith("#") && hex.length === 7) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }
  return hex;
}

