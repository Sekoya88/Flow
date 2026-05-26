"use client";

import { useCallback, useMemo } from "react";
import { ForceGraphCanvas } from "@/components/graph-canvas";
import type {
  BaseGraphLink,
  BaseGraphNode,
  GraphMode,
  LinkRenderState,
  NodeRenderState,
} from "@/components/graph-canvas";
import { NODE_COLORS, NODE_SIZE } from "@/lib/graph/graphColors";

export interface KGNode {
  id: string;
  label: string;
  node_type:
    | "note"
    | "concept"
    | "topic"
    | "query"
    | "trace"
    | "skill"
    | "tool_call"
    | "prompt"
    | "metacog"
    | "agent"
    | "genome_version"
    | "execution"
    | "sub_agent"
    | "system_prompt"
    | "paper";
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
  mode?: GraphMode;
}

interface KGGraphNode extends BaseGraphNode {
  id: string;
  label: string;
  node_type: string;
  summary: string | null;
  pagerank: number;
  cluster_id: number | null;
  color: string;
  val: number;
  _raw: KGNode;
}

type KGGraphLink = BaseGraphLink & { edge_type: string };

const LABEL_ZOOM_THRESHOLD = 1.4;

function nodeRadius(val: number): number {
  return Math.max(2.6, Math.min((val || 4) * 0.7, 9));
}

function withAlpha(hex: string, alpha: number): string {
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

export function KnowledgeGraphCanvas({
  nodes,
  edges,
  highlightedNodeIds,
  className,
  onNodeClick,
  mode = "2d",
}: Props) {
  const graphNodes = useMemo<KGGraphNode[]>(
    () =>
      nodes.map((n) => ({
        id: n.id,
        label: n.label,
        node_type: n.node_type,
        summary: n.summary,
        pagerank: n.pagerank,
        cluster_id: n.cluster_id,
        color:
          NODE_COLORS[n.node_type as keyof typeof NODE_COLORS] ??
          TYPE_COLORS[n.node_type] ??
          "#8b9cb7",
        val:
          NODE_SIZE[n.node_type as keyof typeof NODE_SIZE] ??
          Math.max(2, n.pagerank * 25 + 3),
        _raw: n,
      })),
    [nodes],
  );

  const graphLinks = useMemo<KGGraphLink[]>(() => {
    const ids = new Set(graphNodes.map((n) => n.id));
    return edges
      .filter((e) => ids.has(e.source_id) && ids.has(e.target_id))
      .map((e) => ({
        source: e.source_id,
        target: e.target_id,
        edge_type: e.edge_type,
      }));
  }, [edges, graphNodes]);

  const handleNodeClick = useCallback(
    (node: KGGraphNode) => {
      if (onNodeClick) onNodeClick(node._raw);
    },
    [onNodeClick],
  );

  const renderNode2D = useCallback(
    (
      node: KGGraphNode,
      ctx: CanvasRenderingContext2D,
      globalScale: number,
      state: NodeRenderState,
    ) => {
      const { isHovered, isHighlighted, isIncident, hoveredId } = state;
      const baseRadius = nodeRadius(node.val);
      const radius = isHighlighted || isHovered ? baseRadius * 1.45 : baseRadius;
      const anyFocus = isHighlighted || isHovered || isIncident || hoveredId == null;
      const alpha = anyFocus ? 0.92 : 0.32;

      ctx.shadowBlur = isHighlighted || isHovered ? 22 : isIncident ? 12 : 7;
      ctx.shadowColor = withAlpha(
        node.color,
        isHighlighted || isHovered ? 0.95 : 0.55,
      );

      const nx = (node as unknown as { x?: number }).x ?? 0;
      const ny = (node as unknown as { y?: number }).y ?? 0;

      ctx.beginPath();
      ctx.arc(nx, ny, radius, 0, 2 * Math.PI, false);
      ctx.fillStyle = withAlpha(node.color, alpha);
      ctx.fill();

      ctx.shadowBlur = 0;
      ctx.shadowColor = "transparent";

      ctx.lineWidth = 0.6 / globalScale;
      ctx.strokeStyle = `rgba(15,23,42,${0.65 * alpha})`;
      ctx.stroke();

      if (isHighlighted || isHovered) {
        ctx.beginPath();
        ctx.arc(nx, ny, radius * 2.6, 0, 2 * Math.PI, false);
        ctx.fillStyle = withAlpha(node.color, 0.12);
        ctx.fill();
      }

      const shouldShowLabel =
        isHighlighted ||
        isHovered ||
        isIncident ||
        globalScale > LABEL_ZOOM_THRESHOLD;

      if (shouldShowLabel) {
        const fontSize = Math.max(9, 11 / Math.sqrt(globalScale));
        ctx.font = `500 ${fontSize}px system-ui, -apple-system, sans-serif`;
        const text =
          node.label.length > 36 ? node.label.slice(0, 34) + "…" : node.label;
        const labelY = ny + radius + fontSize + 2;

        ctx.shadowBlur = 5;
        ctx.shadowColor = "rgba(0,0,0,0.95)";
        const baseAlpha = isHighlighted || isHovered ? 1 : 0.82;
        ctx.fillStyle = `rgba(226,232,240,${baseAlpha})`;
        ctx.textAlign = "center";
        ctx.textBaseline = "alphabetic";
        ctx.fillText(text, nx, labelY);
        ctx.shadowBlur = 0;
        ctx.shadowColor = "transparent";
      }
    },
    [],
  );

  const renderPointerArea2D = useCallback(
    (node: KGGraphNode, color: string, ctx: CanvasRenderingContext2D) => {
      const r = nodeRadius(node.val);
      const nx = (node as unknown as { x?: number }).x ?? 0;
      const ny = (node as unknown as { y?: number }).y ?? 0;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(nx, ny, r * 2.4, 0, 2 * Math.PI, false);
      ctx.fill();
    },
    [],
  );

  const linkColor = useCallback(
    (link: KGGraphLink, state: LinkRenderState) => {
      const sourceId =
        typeof link.source === "object"
          ? (link.source as { id: string }).id
          : (link.source as string);
      const targetId =
        typeof link.target === "object"
          ? (link.target as { id: string }).id
          : (link.target as string);
      const incidentToHover =
        state.hoveredId != null &&
        (sourceId === state.hoveredId || targetId === state.hoveredId);
      const incidentToHighlight =
        state.highlightedIds &&
        (state.highlightedIds.has(sourceId) ||
          state.highlightedIds.has(targetId));
      if (incidentToHover || incidentToHighlight) {
        return "rgba(94,234,212,0.65)";
      }
      if (state.hoveredId != null) return "rgba(148,163,184,0.10)";
      return "rgba(148,163,184,0.28)";
    },
    [],
  );

  const linkWidth = useCallback(
    (link: KGGraphLink, state: LinkRenderState) => {
      const sourceId =
        typeof link.source === "object"
          ? (link.source as { id: string }).id
          : (link.source as string);
      const targetId =
        typeof link.target === "object"
          ? (link.target as { id: string }).id
          : (link.target as string);
      const incident =
        state.hoveredId != null &&
        (sourceId === state.hoveredId || targetId === state.hoveredId);
      const highlighted =
        state.highlightedIds &&
        (state.highlightedIds.has(sourceId) ||
          state.highlightedIds.has(targetId));
      if (incident || highlighted) return 1.6;
      return 0.55;
    },
    [],
  );

  const hoverCard = useCallback((node: KGGraphNode) => {
    const raw = node._raw;
    return (
      <div className="absolute top-4 left-4 max-w-80 rounded-[6px] border border-flow-800 bg-card/95 p-5 pointer-events-none z-10 shadow-black/20 animate-fade-in">
        <div className="flex items-center gap-3 mb-3">
          <span
            className="h-3 w-3 rounded-full shrink-0 ring-2 ring-offset-2 ring-offset-card"
            style={{
              backgroundColor: TYPE_COLORS[raw.node_type] ?? "#8b9cb7",
              boxShadow: `0 0 12px ${TYPE_COLORS[raw.node_type] ?? "#8b9cb7"}50`,
            }}
          />
          <span className="text-sm font-semibold text-foreground truncate">
            {raw.label}
          </span>
        </div>
        <div className="flex items-center gap-2 mb-2">
          <span
            className="inline-flex items-center rounded-lg px-2 py-0.5 text-[10px] font-mono font-medium"
            style={{
              backgroundColor: `${TYPE_COLORS[raw.node_type] ?? "#8b9cb7"}15`,
              color: TYPE_COLORS[raw.node_type] ?? "#8b9cb7",
              border: `1px solid ${TYPE_COLORS[raw.node_type] ?? "#8b9cb7"}30`,
            }}
          >
            {raw.node_type.replace("_", " ")}
          </span>
          {raw.pagerank > 0.1 && (
            <span className="text-[10px] text-muted-foreground font-mono tabular-nums">
              PR: {raw.pagerank.toFixed(2)}
            </span>
          )}
          {raw.cluster_id !== null && (
            <span className="text-[10px] text-muted-foreground font-mono">
              Cluster {raw.cluster_id}
            </span>
          )}
        </div>
        {raw.summary && (
          <p className="text-xs text-muted-foreground leading-relaxed line-clamp-4">
            {raw.summary}
          </p>
        )}
      </div>
    );
  }, []);

  return (
    <ForceGraphCanvas<KGGraphNode, KGGraphLink>
      nodes={graphNodes}
      links={graphLinks}
      mode={mode}
      highlightedIds={highlightedNodeIds}
      className={className}
      onNodeClick={handleNodeClick}
      renderNode2D={renderNode2D}
      renderPointerArea2D={renderPointerArea2D}
      linkColor={linkColor}
      linkWidth={linkWidth}
      hoverCard={hoverCard}
    />
  );
}
