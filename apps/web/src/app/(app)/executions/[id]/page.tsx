"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  Background,
  Controls,
  type Edge,
  MiniMap,
  type Node,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  MessageSquare,
  RotateCcw,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

// ── Types ──────────────────────────────────────────────────────────────────

type ReplayNode = { id: string; label: string; visit_count: number; order: number };
type ReplayEdge = { source: string; target: string };
type TimelineEntry = { seq: number; node: string; created_at: string | null };

type ReplayData = {
  execution_id: string;
  status: "running" | "completed" | "failed";
  agent_name: string;
  user_message: string;
  answer: string | null;
  created_at: string | null;
  completed_at: string | null;
  nodes: ReplayNode[];
  edges: ReplayEdge[];
  timeline: TimelineEntry[];
};

// ── Node color palette ─────────────────────────────────────────────────────

const NODE_COLORS: Record<string, string> = {
  planner: "#a855f7",
  worker: "#3b82f6",
  synthesizer: "#10b981",
  reflector: "#f59e0b",
  researcher: "#6366f1",
  critic: "#f43f5e",
  writer: "#14b8a6",
  tool_agent: "#f97316",
  human_gate: "#eab308",
};

function nodeColor(name: string): string {
  return NODE_COLORS[name] ?? "#64748b";
}

// ── XyFlow helpers ─────────────────────────────────────────────────────────

const NODE_W = 160;
const NODE_H = 64;
const GAP_X = 220;

function buildFlowNodes(nodes: ReplayNode[], highlighted: string | null): Node[] {
  return nodes.map((n) => ({
    id: n.id,
    position: { x: n.order * GAP_X, y: 100 },
    data: {
      label: (
        <div className="flex flex-col items-center gap-0.5">
          <span className="font-mono text-xs font-semibold">{n.label}</span>
          {n.visit_count > 1 && (
            <span className="font-mono text-[9px] opacity-70">×{n.visit_count}</span>
          )}
        </div>
      ),
    },
    style: {
      width: NODE_W,
      height: NODE_H,
      borderRadius: 10,
      border: `2px solid ${nodeColor(n.id)}`,
      background:
        highlighted === n.id
          ? `${nodeColor(n.id)}30`
          : "rgba(15,15,20,0.85)",
      color: "#f1f5f9",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      boxShadow:
        highlighted === n.id
          ? `0 0 0 3px ${nodeColor(n.id)}60`
          : "none",
      transition: "all 0.2s",
    },
  }));
}

function buildFlowEdges(edges: ReplayEdge[]): Edge[] {
  return edges.map((e, i) => ({
    id: `${e.source}->${e.target}-${i}`,
    source: e.source,
    target: e.target,
    animated: false,
    style: { stroke: nodeColor(e.source), strokeWidth: 2, opacity: 0.7 },
    markerEnd: { type: "arrowclosed" as const, color: nodeColor(e.source) },
  }));
}

// ── Timeline entry ─────────────────────────────────────────────────────────

function TimelineItem({
  entry,
  active,
  onClick,
}: {
  entry: TimelineEntry;
  active: boolean;
  onClick: () => void;
}) {
  const color = nodeColor(entry.node);
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-2.5 rounded-[6px] px-3 py-2 text-left transition-colors",
        active ? "bg-flow-800" : "hover:bg-flow-900",
      )}
    >
      <span
        className="h-2 w-2 shrink-0 rounded-full"
        style={{ background: color }}
      />
      <span className="flex-1 font-mono text-[11px] text-flow-200">{entry.node}</span>
      <span className="font-mono text-[10px] text-flow-600">#{entry.seq}</span>
    </button>
  );
}

// ── Status badge ───────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: ReplayData["status"] }) {
  if (status === "completed")
    return (
      <Badge className="gap-1 bg-emerald-500/15 font-mono text-[10px] text-emerald-400 border-emerald-500/20">
        <CheckCircle2 className="h-3 w-3" /> completed
      </Badge>
    );
  if (status === "failed")
    return (
      <Badge className="gap-1 bg-destructive/15 font-mono text-[10px] text-destructive border-destructive/20">
        <AlertCircle className="h-3 w-3" /> failed
      </Badge>
    );
  return (
    <Badge className="gap-1 bg-blue-500/15 font-mono text-[10px] text-blue-400 border-blue-500/20">
      <Activity className="h-3 w-3 animate-pulse" /> running
    </Badge>
  );
}

function fmtDuration(start: string | null, end: string | null): string {
  if (!start || !end) return "—";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function ExecutionReplayPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<ReplayData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [highlighted, setHighlighted] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    apiFetch<ReplayData>(`/api/v1/executions/${id}/replay`)
      .then(setData)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [id]);

  const flowNodes = useMemo(
    () => (data ? buildFlowNodes(data.nodes, highlighted) : []),
    [data, highlighted],
  );
  const flowEdges = useMemo(
    () => (data ? buildFlowEdges(data.edges) : []),
    [data],
  );

  const [rfNodes, setRfNodes, onRfNodesChange] = useNodesState<Node>([]);
  const [rfEdges, setRfEdges, onRfEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => { setRfNodes(flowNodes); }, [flowNodes, setRfNodes]);
  useEffect(() => { setRfEdges(flowEdges); }, [flowEdges, setRfEdges]);

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-flow-500" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-[60vh] flex-col items-center justify-center gap-3">
        <AlertCircle className="h-6 w-6 text-destructive" />
        <p className="font-mono text-xs text-flow-500">{error ?? "Not found"}</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="font-mono text-sm font-semibold text-flow-50">
              {data.agent_name}
            </h2>
            <StatusBadge status={data.status} />
          </div>
          <p className="mt-0.5 truncate font-mono text-[11px] text-flow-500">
            {data.user_message}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3 font-mono text-[10px] text-flow-600">
          <span className="flex items-center gap-1">
            <RotateCcw className="h-3 w-3" />
            {data.nodes.length} nodes
          </span>
          <span className="flex items-center gap-1">
            <Activity className="h-3 w-3" />
            {data.timeline.length} steps
          </span>
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {fmtDuration(data.created_at, data.completed_at)}
          </span>
        </div>
      </div>

      {/* Canvas + timeline */}
      <div className="flex flex-1 gap-4 overflow-hidden">
        {/* XyFlow canvas */}
        <div className="flex-1 overflow-hidden rounded-[10px] border border-flow-800 bg-flow-950">
          {data.nodes.length === 0 ? (
            <div className="flex h-full items-center justify-center">
              <div className="flex flex-col items-center gap-2 text-center">
                <MessageSquare className="h-7 w-7 text-flow-700" />
                <p className="font-mono text-xs text-flow-500">No node events recorded yet.</p>
              </div>
            </div>
          ) : (
            <ReactFlow
              nodes={rfNodes}
              edges={rfEdges}
              onNodesChange={onRfNodesChange}
              onEdgesChange={onRfEdgesChange}
              onNodeClick={(_, node) =>
                setHighlighted((h) => (h === node.id ? null : node.id))
              }
              fitView
              fitViewOptions={{ padding: 0.3 }}
              minZoom={0.3}
              maxZoom={2}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={false}
            >
              <Background gap={24} size={1} color="rgba(255,255,255,0.03)" />
              <Controls showInteractive={false} className="!bg-flow-900 !border-flow-700" />
              <MiniMap
                className="!bg-flow-900/90 !border-flow-800"
                maskColor="rgba(0,0,0,0.3)"
                nodeColor={(n) => nodeColor(n.id)}
              />
            </ReactFlow>
          )}
        </div>

        {/* Timeline panel */}
        <div className="flex w-52 shrink-0 flex-col rounded-[10px] border border-flow-800 bg-flow-950">
          <div className="border-b border-flow-800 px-3 py-2.5">
            <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-flow-500">
              Timeline
            </h3>
          </div>
          <div className="flex-1 overflow-y-auto p-1.5">
            {data.timeline.length === 0 ? (
              <p className="px-2 py-4 text-center font-mono text-[10px] text-flow-600">
                No steps yet
              </p>
            ) : (
              data.timeline.map((entry) => (
                <TimelineItem
                  key={entry.seq}
                  entry={entry}
                  active={highlighted === entry.node}
                  onClick={() =>
                    setHighlighted((h) => (h === entry.node ? null : entry.node))
                  }
                />
              ))
            )}
          </div>
        </div>
      </div>

      {/* Answer strip */}
      {data.answer && (
        <div className="rounded-[8px] border border-flow-800 bg-flow-900/50 p-3">
          <p className="mb-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-flow-600">
            Answer
          </p>
          <p className="line-clamp-3 text-xs leading-relaxed text-flow-300">{data.answer}</p>
        </div>
      )}
    </div>
  );
}
