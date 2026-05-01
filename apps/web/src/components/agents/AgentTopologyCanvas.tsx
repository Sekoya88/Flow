"use client";

import { useCallback, useEffect, useMemo } from "react";
import {
  Background,
  Controls,
  type Edge,
  type Node,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

export type CatalogNode = { id: string; label: string; x: number; y: number };
export type CatalogEdge = { source: string; target: string; kind: string; label: string | null };

type Props = {
  graphId: string;
  nodes: CatalogNode[];
  edges: CatalogEdge[];
  className?: string;
};

function toFlowNodes(nodes: CatalogNode[]): Node[] {
  return nodes.map((n) => ({
    id: n.id,
    position: { x: n.x, y: n.y },
    data: { label: n.label },
    style: {
      fontSize: 12,
      borderRadius: 8,
      padding: "8px 12px",
      border: "1px solid var(--border, #e5e5e5)",
      background: "var(--card, #fafafa)",
    },
  }));
}

function toFlowEdges(edges: CatalogEdge[]): Edge[] {
  return edges.map((e, i) => ({
    id: `${e.source}-${e.target}-${i}`,
    source: e.source,
    target: e.target,
    label: e.label ?? undefined,
    animated: e.kind === "conditional",
    style:
      e.kind === "conditional"
        ? { strokeDasharray: "4 4", stroke: "var(--color-flow-thinking, #a855f7)" }
        : { stroke: "var(--color-flow-brand, #6366f1)" },
  }));
}

export function AgentTopologyCanvas({ graphId, nodes: inNodes, edges: inEdges, className }: Props) {
  const initialNodes = useMemo(() => toFlowNodes(inNodes), [inNodes]);
  const initialEdges = useMemo(() => toFlowEdges(inEdges), [inEdges]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(toFlowNodes(inNodes));
    setEdges(toFlowEdges(inEdges));
  }, [graphId, inNodes, inEdges, setNodes, setEdges]);

  const onInit = useCallback(
    (instance: { fitView: (opts?: { padding?: number }) => void }) => {
      requestAnimationFrame(() => instance.fitView({ padding: 0.2 }));
    },
    [],
  );

  return (
    <div className={className ?? "h-[min(70vh,560px)] w-full rounded-xl border border-border/60 bg-muted/10"}>
      <ReactFlow
        key={graphId}
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onInit={onInit}
        fitView
        minZoom={0.4}
        maxZoom={1.4}
      >
        <Background gap={20} size={1} color="var(--border)" />
        <Controls showInteractive={false} />
        <MiniMap
          className="!bg-card/90"
          maskColor="rgba(0,0,0,0.12)"
          nodeColor={() => "var(--color-flow-brand, #6366f1)"}
        />
      </ReactFlow>
    </div>
  );
}
