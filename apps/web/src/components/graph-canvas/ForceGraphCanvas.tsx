"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import dynamic from "next/dynamic";
import { cn } from "@/lib/utils";
import type {
  BaseGraphLink,
  BaseGraphNode,
  ForceGraphPhysics,
  GraphMode,
  LinkRenderState,
  NodeRenderState,
} from "./types";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });
const ForceGraph3D = dynamic(() => import("react-force-graph-3d"), { ssr: false });

export interface ForceGraphCanvasProps<
  N extends BaseGraphNode = BaseGraphNode,
  L extends BaseGraphLink = BaseGraphLink,
> {
  nodes: N[];
  links: L[];
  mode?: GraphMode;
  highlightedIds?: Set<string>;
  className?: string;
  onNodeClick?: (node: N) => void;
  onNodeHover?: (node: N | null) => void;
  renderNode2D?: (
    node: N,
    ctx: CanvasRenderingContext2D,
    globalScale: number,
    state: NodeRenderState,
  ) => void;
  renderPointerArea2D?: (
    node: N,
    color: string,
    ctx: CanvasRenderingContext2D,
  ) => void;
  nodeThreeObject?: (node: N) => unknown;
  linkColor?: (link: L, state: LinkRenderState) => string;
  linkWidth?: (link: L, state: LinkRenderState) => number;
  hoverCard?: (node: N) => ReactNode;
  physics?: ForceGraphPhysics;
  /** Auto-fit camera to bounds after physics settles. Default: true. */
  autoFit?: boolean;
  /** Relative node size passed to react-force-graph. */
  nodeRelSize?: number;
}

const DEFAULT_PHYSICS: Required<ForceGraphPhysics> = {
  chargeStrength: -420,
  linkDistance: 120,
  linkStrength: 0.15,
  centerStrength: 0.02,
  warmupTicks: 120,
  cooldownTicks: 300,
  cooldownTime: 4000,
  alphaDecay: 0.02,
  velocityDecay: 0.4,
};

function defaultLinkColor(_link: BaseGraphLink, state: LinkRenderState): string {
  if (state.hoveredId != null) return "rgba(148,163,184,0.10)";
  return "rgba(148,163,184,0.28)";
}

function defaultLinkWidth(): number {
  return 0.55;
}

export function ForceGraphCanvas<
  N extends BaseGraphNode = BaseGraphNode,
  L extends BaseGraphLink = BaseGraphLink,
>({
  nodes,
  links,
  mode = "2d",
  highlightedIds,
  className,
  onNodeClick,
  onNodeHover,
  renderNode2D,
  renderPointerArea2D,
  nodeThreeObject,
  linkColor,
  linkWidth,
  hoverCard,
  physics,
  autoFit = true,
  nodeRelSize = 2.4,
}: ForceGraphCanvasProps<N, L>) {
  const fgRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<N | null>(null);
  const fittedRef = useRef(false);

  const resolvedPhysics = { ...DEFAULT_PHYSICS, ...physics };

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({
        width: Math.max(width, 200),
        height: Math.max(height, 200),
      });
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const graphData = useMemo(() => ({ nodes, links }), [nodes, links]);

  const adjacency = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const link of links) {
      const a =
        typeof link.source === "object"
          ? (link.source as BaseGraphNode).id
          : link.source;
      const b =
        typeof link.target === "object"
          ? (link.target as BaseGraphNode).id
          : link.target;
      if (!map.has(a)) map.set(a, new Set());
      if (!map.has(b)) map.set(b, new Set());
      map.get(a)!.add(b);
      map.get(b)!.add(a);
    }
    return map;
  }, [links]);

  const handleNodeClick = useCallback(
    (node: any) => {
      if (onNodeClick) onNodeClick(node as N);
      if (fgRef.current && mode === "2d") {
        try {
          fgRef.current.centerAt?.(node.x ?? 0, node.y ?? 0, 600);
          fgRef.current.zoom?.(3.2, 600);
        } catch {
          /* ignore */
        }
      }
    },
    [onNodeClick, mode],
  );

  const handleNodeHoverInternal = useCallback(
    (node: any) => {
      const next = (node as N | null) ?? null;
      setHoveredNode(next);
      setHoveredId(next?.id ?? null);
      if (onNodeHover) onNodeHover(next);
    },
    [onNodeHover],
  );

  // Auto-fit on mount + after a settle period.
  useEffect(() => {
    fittedRef.current = false;
    if (!autoFit || nodes.length === 0) return;
    const timers: number[] = [];
    const fit = () => {
      if (fgRef.current) {
        try {
          fgRef.current.zoomToFit?.(400, 60);
        } catch {
          /* ignore */
        }
      }
    };
    timers.push(window.setTimeout(fit, 400));
    timers.push(
      window.setTimeout(() => {
        fit();
        fittedRef.current = true;
      }, 1200),
    );
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [nodes.length, autoFit, mode]);

  // Tune d3 forces (2D only — 3D has its own defaults that read fine).
  useEffect(() => {
    if (mode !== "2d") return;
    const fg = fgRef.current;
    if (!fg || nodes.length === 0) return;
    let cancelled = false;
    const apply = () => {
      if (cancelled || !fgRef.current) return;
      try {
        const charge = fg.d3Force?.("charge");
        if (charge?.strength) charge.strength(resolvedPhysics.chargeStrength);
        const link = fg.d3Force?.("link");
        if (link?.distance) link.distance(resolvedPhysics.linkDistance);
        if (link?.strength) link.strength(resolvedPhysics.linkStrength);
        const center = fg.d3Force?.("center");
        if (center?.strength) center.strength(resolvedPhysics.centerStrength);
      } catch {
        /* ignore — defaults still acceptable */
      }
    };
    apply();
    const t = window.setTimeout(apply, 80);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, [
    nodes.length,
    mode,
    resolvedPhysics.chargeStrength,
    resolvedPhysics.linkDistance,
    resolvedPhysics.linkStrength,
    resolvedPhysics.centerStrength,
  ]);

  const handleEngineStop = useCallback(() => {
    if (!autoFit) return;
    if (!fittedRef.current && fgRef.current && nodes.length > 0) {
      fittedRef.current = true;
      try {
        fgRef.current.zoomToFit?.(400, 80);
      } catch {
        /* ignore */
      }
    }
  }, [nodes.length, autoFit]);

  const linkState: LinkRenderState = { hoveredId, highlightedIds };

  const linkColorResolved = useCallback(
    (link: any) => (linkColor ?? defaultLinkColor)(link as L, linkState),
    [linkColor, hoveredId, highlightedIds],
  );

  const linkWidthResolved = useCallback(
    (link: any) => (linkWidth ?? defaultLinkWidth)(link as L, linkState),
    [linkWidth, hoveredId, highlightedIds],
  );

  // 2D canvas renderer with state baked in.
  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      if (!renderNode2D) return;
      const state: NodeRenderState = {
        isHovered: hoveredId === node.id,
        isHighlighted: highlightedIds?.has(node.id) ?? false,
        isIncident:
          hoveredId != null && adjacency.get(hoveredId)?.has(node.id) === true,
        hoveredId,
      };
      renderNode2D(node as N, ctx, globalScale, state);
    },
    [renderNode2D, hoveredId, highlightedIds, adjacency],
  );

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative h-full w-full overflow-hidden rounded-[6px]",
        className,
      )}
      data-testid="force-graph-canvas"
      data-mode={mode}
    >
      {nodes.length > 0 && mode === "2d" && (
        <ForceGraph2D
          ref={fgRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          nodeCanvasObject={renderNode2D ? nodeCanvasObject : undefined}
          nodeCanvasObjectMode={renderNode2D ? () => "replace" : undefined}
          nodePointerAreaPaint={renderPointerArea2D as any}
          linkColor={linkColorResolved}
          linkWidth={linkWidthResolved}
          linkLineDash={() => null}
          backgroundColor="rgba(0,0,0,0)"
          onNodeClick={handleNodeClick}
          onNodeHover={handleNodeHoverInternal}
          enableNodeDrag={true}
          enableZoomInteraction={true}
          enablePanInteraction={true}
          warmupTicks={resolvedPhysics.warmupTicks}
          cooldownTicks={resolvedPhysics.cooldownTicks}
          cooldownTime={resolvedPhysics.cooldownTime}
          d3AlphaDecay={resolvedPhysics.alphaDecay}
          d3VelocityDecay={resolvedPhysics.velocityDecay}
          nodeRelSize={nodeRelSize}
          onEngineStop={handleEngineStop}
        />
      )}

      {nodes.length > 0 && mode === "3d" && (
        <ForceGraph3D
          ref={fgRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          nodeThreeObject={nodeThreeObject as any}
          nodeLabel={(n: any) => (n.label ?? n.id) as string}
          linkColor={linkColorResolved as any}
          linkWidth={linkWidthResolved as any}
          backgroundColor="rgba(0,0,0,0)"
          onNodeClick={handleNodeClick}
          onNodeHover={handleNodeHoverInternal}
          warmupTicks={resolvedPhysics.warmupTicks}
          cooldownTicks={resolvedPhysics.cooldownTicks}
          cooldownTime={resolvedPhysics.cooldownTime}
          nodeRelSize={nodeRelSize}
          onEngineStop={handleEngineStop}
        />
      )}

      {hoveredNode && hoverCard ? hoverCard(hoveredNode) : null}
    </div>
  );
}
