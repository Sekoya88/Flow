"use client";

import { useCallback, useEffect, useMemo } from "react";
import {
  Background,
  Controls,
  type Edge,
  Handle,
  type Node,
  MiniMap,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { cn } from "@/lib/utils";

export interface KGNode {
  id: string;
  label: string;
  node_type: "note" | "concept" | "topic" | "query";
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

interface Props {
  nodes: KGNode[];
  edges: KGEdge[];
  highlightedNodeIds?: Set<string>;
  highlightedPath?: string[];
  onNodeClick?: (node: KGNode) => void;
  className?: string;
}

const CLUSTER_COLORS: Record<number, { bg: string; border: string; text: string }> = {
  0: { bg: "rgba(99,102,241,0.15)", border: "#6366f1", text: "#a5b4fc" },
  1: { bg: "rgba(16,185,129,0.15)", border: "#10b981", text: "#6ee7b7" },
  2: { bg: "rgba(245,158,11,0.15)", border: "#f59e0b", text: "#fcd34d" },
  3: { bg: "rgba(236,72,153,0.15)", border: "#ec4899", text: "#f9a8d4" },
  4: { bg: "rgba(14,165,233,0.15)", border: "#0ea5e9", text: "#7dd3fc" },
  5: { bg: "rgba(168,85,247,0.15)", border: "#a855f7", text: "#d8b4fe" },
};

const TYPE_SHAPE: Record<string, string> = {
  note: "rounded-lg",
  concept: "rounded-full",
  topic: "rounded-sm",
  query: "rounded-lg border-dashed",
};

function KGNodeComponent({ data }: { data: KGNode & { highlighted: boolean; inPath: boolean } }) {
  const clusterColor = CLUSTER_COLORS[(data.cluster_id ?? 0) % Object.keys(CLUSTER_COLORS).length] ?? CLUSTER_COLORS[0];
  const size = Math.max(32, Math.min(80, 32 + data.pagerank * 120));
  const shapeClass = TYPE_SHAPE[data.node_type] ?? "rounded-lg";

  return (
    <div
      style={{
        width: size,
        height: size,
        background: data.highlighted || data.inPath ? clusterColor.border : clusterColor.bg,
        borderColor: data.inPath ? "#ffffff" : clusterColor.border,
        borderWidth: data.inPath ? 2 : 1,
        boxShadow: (data.highlighted || data.inPath) ? `0 0 16px ${clusterColor.border}88` : undefined,
        fontSize: Math.max(8, Math.min(11, size * 0.18)),
        transition: "all 0.2s ease",
      }}
      className={cn(
        "flex items-center justify-center border text-center cursor-pointer select-none",
        "text-[11px] font-medium leading-tight px-1",
        shapeClass,
      )}
      title={data.summary ?? data.label}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <span style={{ color: data.highlighted ? "#fff" : clusterColor.text }}>
        {data.label.length > 14 ? data.label.slice(0, 12) + "…" : data.label}
      </span>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = { kg: KGNodeComponent };

function toFlowNodes(
  kgNodes: KGNode[],
  highlightedIds: Set<string>,
  pathLabels: Set<string>,
): Node[] {
  return kgNodes.map((n) => ({
    id: n.id,
    type: "kg" as const,
    position: { x: n.pos_x, y: n.pos_y },
    data: {
      ...n,
      highlighted: highlightedIds.has(n.id),
      inPath: pathLabels.has(n.label),
    },
  }));
}

function toFlowEdges(kgEdges: KGEdge[], pathLabels: Set<string>, kgNodes: KGNode[]): Edge[] {
  const labelById = Object.fromEntries(kgNodes.map((n) => [n.id, n.label]));
  return kgEdges.map((e) => {
    const srcLabel = labelById[e.source_id] ?? "";
    const tgtLabel = labelById[e.target_id] ?? "";
    const inPath = pathLabels.has(srcLabel) && pathLabels.has(tgtLabel);
    return {
      id: e.id,
      source: e.source_id,
      target: e.target_id,
      animated: inPath,
      style: {
        stroke: inPath ? "#6366f1" : e.edge_type === "similar_to" ? "#334155" : "#1e293b",
        strokeWidth: inPath ? 2 : 1,
        strokeDasharray: e.edge_type === "similar_to" ? "4 3" : undefined,
        opacity: inPath ? 0.9 : 0.4,
      },
    };
  });
}

export function KnowledgeGraphCanvas({
  nodes: kgNodes,
  edges: kgEdges,
  highlightedNodeIds = new Set(),
  highlightedPath = [],
  onNodeClick,
  className,
}: Props) {
  const pathLabels = useMemo(() => new Set(highlightedPath), [highlightedPath]);

  const initialNodes = useMemo(
    () => toFlowNodes(kgNodes, highlightedNodeIds, pathLabels),
    [kgNodes, highlightedNodeIds, pathLabels],
  );
  const initialEdges = useMemo(
    () => toFlowEdges(kgEdges, pathLabels, kgNodes),
    [kgEdges, pathLabels, kgNodes],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(toFlowNodes(kgNodes, highlightedNodeIds, pathLabels));
    setEdges(toFlowEdges(kgEdges, pathLabels, kgNodes));
  }, [kgNodes, kgEdges, highlightedNodeIds, pathLabels, setNodes, setEdges]);

  const onInit = useCallback(
    (instance: { fitView: (opts?: { padding?: number }) => void }) => {
      requestAnimationFrame(() => instance.fitView({ padding: 0.12 }));
    },
    [],
  );

  const handleNodeClick = useCallback(
    (_: unknown, node: Node) => {
      const kg = kgNodes.find((n) => n.id === node.id);
      if (kg && onNodeClick) onNodeClick(kg);
    },
    [kgNodes, onNodeClick],
  );

  return (
    <div className={cn("h-full w-full", className)}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onInit={onInit}
        onNodeClick={handleNodeClick}
        fitView
        minZoom={0.15}
        maxZoom={2}
        className="bg-[#060a12]"
      >
        <Background gap={24} size={1} color="#1e293b" />
        <Controls
          showInteractive={false}
          className="!bg-[#0f172a] !border-[#1e293b] [&>button]:!bg-[#0f172a] [&>button]:!border-[#1e293b] [&>button]:!text-slate-400 [&>button:hover]:!bg-[#1e293b]"
        />
        <MiniMap
          className="!bg-[#0a0f1a]/90 !border-[#1e293b]"
          maskColor="rgba(0,0,0,0.3)"
          nodeColor={(n) => {
            const data = n.data as Record<string, unknown>;
            const cluster = (typeof data.cluster_id === "number" ? data.cluster_id : 0);
            return CLUSTER_COLORS[cluster % Object.keys(CLUSTER_COLORS).length]?.border ?? "#6366f1";
          }}
        />
      </ReactFlow>
    </div>
  );
}
