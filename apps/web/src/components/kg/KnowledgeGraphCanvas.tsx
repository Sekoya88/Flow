"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import * as THREE from "three";
import { cn } from "@/lib/utils";

const ForceGraph3D = dynamic(() => import("react-force-graph-3d"), { ssr: false });

export interface KGNode {
  id: string;
  label: string;
  node_type: "note" | "concept" | "topic" | "query" | "trace" | "skill" | "tool_call" | "prompt" | "metacog";
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
  tool_call: "#fbbf24",
  trace: "#38bdf8",
  metacog: "#a78bfa",
  prompt: "#818cf8",
  note: "#8b9cb7",
  topic: "#67e8f9",
  query: "#7dd3fc",
};

interface Props {
  nodes: KGNode[];
  edges: KGEdge[];
  highlightedNodeIds?: Set<string>;
  highlightedPath?: string[];
  className?: string;
  onNodeClick?: (node: KGNode) => void;
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
    const gNodes = nodes.map((n) => ({
      id: n.id,
      label: n.label,
      node_type: n.node_type,
      summary: n.summary,
      pagerank: n.pagerank,
      cluster_id: n.cluster_id,
      color: TYPE_COLORS[n.node_type] || "#8b9cb7",
      val: Math.max(2, n.pagerank * 25 + 3),
      _raw: n,
    }));
    const nodeIds = new Set(gNodes.map((n) => n.id));
    const gLinks = edges
      .filter((e) => nodeIds.has(e.source_id) && nodeIds.has(e.target_id))
      .map((e) => ({
        source: e.source_id,
        target: e.target_id,
        edge_type: e.edge_type,
      }));
    return { nodes: gNodes, links: gLinks };
  }, [nodes, edges]);

  const handleNodeClick = useCallback((node: any) => {
    if (onNodeClick && node._raw) onNodeClick(node._raw);
    if (fgRef.current) {
      const distance = 120;
      const distRatio = 1 + distance / Math.hypot(node.x || 1, node.y || 1, node.z || 1);
      fgRef.current.cameraPosition(
        { x: (node.x || 0) * distRatio, y: (node.y || 0) * distRatio, z: (node.z || 0) * distRatio },
        node,
        1000,
      );
    }
  }, [onNodeClick]);

  const nodeThreeObject = useCallback((node: any) => {
    const isHighlighted = highlightedNodeIds?.has(node.id);
    const radius = node.val * (isHighlighted ? 1.5 : 1);

    const group = new THREE.Group();

    // Core sphere with improved material
    const geometry = new THREE.SphereGeometry(radius, 32, 32);
    const material = new THREE.MeshStandardMaterial({
      color: node.color,
      transparent: true,
      opacity: isHighlighted ? 0.95 : 0.75,
      roughness: 0.2,
      metalness: 0.15,
      emissive: node.color,
      emissiveIntensity: isHighlighted ? 0.5 : 0.12,
    });
    const sphere = new THREE.Mesh(geometry, material);
    group.add(sphere);

    // Inner glow for all nodes (not just large ones)
    const glowGeo = new THREE.SphereGeometry(radius * 1.8, 16, 16);
    const glowMat = new THREE.MeshBasicMaterial({
      color: node.color,
      transparent: true,
      opacity: isHighlighted ? 0.12 : 0.04,
    });
    group.add(new THREE.Mesh(glowGeo, glowMat));

    // Outer ambient glow for highlighted nodes
    if (isHighlighted) {
      const outerGeo = new THREE.SphereGeometry(radius * 2.8, 12, 12);
      const outerMat = new THREE.MeshBasicMaterial({
        color: node.color,
        transparent: true,
        opacity: 0.06,
      });
      group.add(new THREE.Mesh(outerGeo, outerMat));
    }

    // Text label with background — floor prevents invisible labels on tiny nodes
    const labelW = Math.max(radius * 6, 16);
    const labelH = Math.max(radius * 2.2, 6);
    const sprite = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: createTextTexture(node.label, node.color, isHighlighted ?? false),
        transparent: true,
        depthWrite: false,
        opacity: isHighlighted ? 1 : 0.92,
      }),
    );
    sprite.scale.set(labelW, labelH, 1);
    sprite.position.y = radius + 5;
    group.add(sprite);

    return group;
  }, [highlightedNodeIds]);

  return (
    <div ref={containerRef} className={cn("relative h-full w-full overflow-hidden rounded-2xl", className)}>
      {graphData.nodes.length > 0 && (
        <ForceGraph3D
          ref={fgRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          nodeThreeObject={nodeThreeObject}
          nodeThreeObjectExtend={false}
          linkColor={() => "rgba(148,163,184,0.15)"}
          linkWidth={0.5}
          linkOpacity={0.4}
          linkDirectionalParticles={2}
          linkDirectionalParticleWidth={1.2}
          linkDirectionalParticleSpeed={0.004}
          linkDirectionalParticleColor={() => "rgba(94,234,212,0.5)"}
          backgroundColor="rgba(0,0,0,0)"
          onNodeClick={handleNodeClick}
          onNodeHover={(node: any) => setHoveredNode(node?._raw ?? null)}
          enableNodeDrag={true}
          enableNavigationControls={true}
          showNavInfo={false}
          warmupTicks={80}
          cooldownTicks={150}
          d3AlphaDecay={0.018}
          d3VelocityDecay={0.25}
        />
      )}

      {/* Hover card — polished */}
      {hoveredNode && (
        <div className="absolute top-4 left-4 max-w-80 rounded-2xl border border-border/50 bg-card/95 backdrop-blur-2xl p-5 pointer-events-none z-10 shadow-2xl shadow-black/20 animate-fade-in">
          <div className="flex items-center gap-3 mb-3">
            <span
              className="h-3 w-3 rounded-full shrink-0 ring-2 ring-offset-2 ring-offset-card"
              style={{
                backgroundColor: TYPE_COLORS[hoveredNode.node_type],
                boxShadow: `0 0 12px ${TYPE_COLORS[hoveredNode.node_type]}50`,
              }}
            />
            <span className="text-sm font-semibold text-foreground truncate">{hoveredNode.label}</span>
          </div>
          <div className="flex items-center gap-2 mb-2">
            <span
              className="inline-flex items-center rounded-lg px-2 py-0.5 text-[10px] font-mono font-medium"
              style={{
                backgroundColor: `${TYPE_COLORS[hoveredNode.node_type]}15`,
                color: TYPE_COLORS[hoveredNode.node_type],
                border: `1px solid ${TYPE_COLORS[hoveredNode.node_type]}30`,
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

function createTextTexture(text: string, color: string, highlighted: boolean): any {
  if (typeof document === "undefined") return null;
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  canvas.width = 512;
  canvas.height = 96;

  // Background pill
  const label = text.length > 32 ? text.slice(0, 30) + "…" : text;
  ctx.font = "600 26px system-ui, -apple-system, sans-serif";
  const textWidth = ctx.measureText(label).width;
  const pillWidth = Math.min(textWidth + 28, 500);
  const pillHeight = 40;
  const x = (512 - pillWidth) / 2;
  const y = (96 - pillHeight) / 2;

  // Draw rounded rect background
  ctx.fillStyle = highlighted ? "rgba(0,0,0,0.6)" : "rgba(0,0,0,0.35)";
  ctx.beginPath();
  const r = 10;
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + pillWidth - r, y);
  ctx.quadraticCurveTo(x + pillWidth, y, x + pillWidth, y + r);
  ctx.lineTo(x + pillWidth, y + pillHeight - r);
  ctx.quadraticCurveTo(x + pillWidth, y + pillHeight, x + pillWidth - r, y + pillHeight);
  ctx.lineTo(x + r, y + pillHeight);
  ctx.quadraticCurveTo(x, y + pillHeight, x, y + pillHeight - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
  ctx.fill();

  // Draw text
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = highlighted ? "rgba(255,255,255,0.95)" : "rgba(226,232,240,0.85)";
  ctx.fillText(label, 256, 48);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}
