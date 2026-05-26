"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Background,
  Controls,
  type Edge,
  MiniMap,
  type Node,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type OnSelectionChangeParams,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Activity,
  AlertCircle,
  Bot,
  Loader2,
  Plus,
  Search,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiFetch } from "@/lib/api";
import { NODE_COLORS } from "@/lib/graph/graphColors";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { KGNode } from "@/components/kg/KnowledgeGraphCanvas";

// ── Types ──────────────────────────────────────────────────────────────────

type AgentRow = { id: string; name: string; template: string };

type CanvasItem = {
  kgId: string;
  label: string;
  node_type: string;
  summary: string | null;
  x: number;
  y: number;
};

// ── Colors ─────────────────────────────────────────────────────────────────

function nodeTypeColor(t: string): string {
  return (NODE_COLORS as Record<string, string>)[t] ?? "#64748b";
}

// ── Canvas node builder ────────────────────────────────────────────────────

function buildFlowNode(item: CanvasItem, selected: boolean): Node {
  const color = nodeTypeColor(item.node_type);
  return {
    id: item.kgId,
    position: { x: item.x, y: item.y },
    data: {
      label: (
        <div className="flex flex-col items-start gap-0.5 p-0.5">
          <span className="font-mono text-[10px] font-semibold leading-tight">{item.label}</span>
          <span
            className="rounded-[3px] px-1 font-mono text-[8px] uppercase tracking-wide"
            style={{ background: `${color}20`, color }}
          >
            {item.node_type}
          </span>
        </div>
      ),
    },
    style: {
      width: 160,
      minHeight: 52,
      borderRadius: 10,
      border: `2px solid ${selected ? color : `${color}60`}`,
      background: selected ? `${color}18` : "rgba(10,12,18,0.9)",
      color: "#f1f5f9",
      boxShadow: selected ? `0 0 0 3px ${color}40` : "none",
      transition: "all 0.15s",
      cursor: "grab",
      display: "flex",
      alignItems: "center",
      justifyContent: "flex-start",
      padding: "8px 10px",
    },
  };
}

// ── Sidebar node item ──────────────────────────────────────────────────────

function KGNodeItem({
  node,
  onAdd,
}: {
  node: KGNode;
  onAdd: (node: KGNode) => void;
}) {
  const color = nodeTypeColor(node.node_type);
  return (
    <div
      draggable
      onDragStart={(e) => e.dataTransfer.setData("kg-node-id", node.id)}
      className="flex cursor-grab items-start gap-2 rounded-[6px] border border-flow-800 bg-flow-900/50 px-2.5 py-2 hover:bg-flow-800/70 transition-colors"
    >
      <span
        className="mt-0.5 h-2 w-2 shrink-0 rounded-full"
        style={{ background: color }}
      />
      <div className="min-w-0 flex-1">
        <p className="truncate font-mono text-[11px] font-medium text-flow-100">{node.label}</p>
        {node.summary && (
          <p className="line-clamp-1 text-[10px] text-flow-600">{node.summary}</p>
        )}
      </div>
      <button
        onClick={() => onAdd(node)}
        className="shrink-0 rounded-[4px] p-0.5 text-flow-600 hover:bg-flow-700 hover:text-flow-200 transition-colors"
      >
        <Plus className="h-3 w-3" />
      </button>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function WorkbenchPage() {
  const wsId = useStore((s) => s.workspaces[0]?.id ?? "");

  // KG data
  const [kgNodes, setKgNodes] = useState<KGNode[]>([]);
  const [kgSearch, setKgSearch] = useState("");
  const [loadingKg, setLoadingKg] = useState(false);

  // Agents
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [agentId, setAgentId] = useState("");

  // Canvas
  const [canvasItems, setCanvasItems] = useState<CanvasItem[]>([]);
  const [rfNodes, setRfNodes, onRfNodesChange] = useNodesState<Node>([]);
  const [rfEdges, , onRfEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNodeIds, setSelectedNodeIds] = useState<Set<string>>(new Set());
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  // Run state
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [runExecId, setRunExecId] = useState<string | null>(null);

  // Load KG nodes
  useEffect(() => {
    if (!wsId) return;
    setLoadingKg(true);
    apiFetch<{ nodes: KGNode[] }>(`/api/v1/kg/graph?workspace_id=${wsId}`)
      .then((d) => setKgNodes(d.nodes ?? []))
      .catch(() => setKgNodes([]))
      .finally(() => setLoadingKg(false));
  }, [wsId]);

  // Load agents
  useEffect(() => {
    if (!wsId) return;
    apiFetch<{ agents: AgentRow[] }>(`/api/v1/workspaces/${wsId}/agents`)
      .then((d) => {
        setAgents(d.agents ?? []);
        if (d.agents?.[0]) setAgentId(d.agents[0].id);
      })
      .catch(() => {});
  }, [wsId]);

  // Sync canvas items → XyFlow nodes
  useEffect(() => {
    setRfNodes(
      canvasItems.map((item) =>
        buildFlowNode(item, selectedNodeIds.has(item.kgId)),
      ),
    );
  }, [canvasItems, selectedNodeIds, setRfNodes]);

  function addNodeToCanvas(node: KGNode, x?: number, y?: number) {
    if (canvasItems.find((c) => c.kgId === node.id)) return;
    const offset = canvasItems.length;
    setCanvasItems((prev) => [
      ...prev,
      {
        kgId: node.id,
        label: node.label,
        node_type: node.node_type,
        summary: node.summary,
        x: x ?? 40 + (offset % 4) * 200,
        y: y ?? 40 + Math.floor(offset / 4) * 140,
      },
    ]);
  }

  function removeNode(kgId: string) {
    setCanvasItems((prev) => prev.filter((c) => c.kgId !== kgId));
    setSelectedNodeIds((prev) => {
      const next = new Set(prev);
      next.delete(kgId);
      return next;
    });
  }

  function clearCanvas() {
    setCanvasItems([]);
    setSelectedNodeIds(new Set());
    setRunResult(null);
    setRunError(null);
  }

  const onSelectionChange = useCallback(({ nodes }: OnSelectionChangeParams) => {
    setSelectedNodeIds(new Set(nodes.map((n) => n.id)));
  }, []);

  // Drop from sidebar
  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      const kgId = e.dataTransfer.getData("kg-node-id");
      if (!kgId) return;
      const node = kgNodes.find((n) => n.id === kgId);
      if (!node) return;
      const bounds = reactFlowWrapper.current?.getBoundingClientRect();
      const x = bounds ? e.clientX - bounds.left - 80 : 200;
      const y = bounds ? e.clientY - bounds.top - 26 : 120;
      addNodeToCanvas(node, x, y);
    },
    [kgNodes, canvasItems],
  );

  async function runOnCluster() {
    const targets =
      selectedNodeIds.size > 0
        ? canvasItems.filter((c) => selectedNodeIds.has(c.kgId))
        : canvasItems;
    if (!agentId || targets.length === 0) return;

    const context = targets
      .map((n) => `- ${n.label}${n.summary ? `: ${n.summary}` : ""}`)
      .join("\n");
    const message = `Analyze and synthesize the following knowledge graph nodes:\n\n${context}\n\nProvide insights, connections, and key takeaways.`;

    setRunning(true);
    setRunResult(null);
    setRunError(null);
    setRunExecId(null);
    try {
      const res = await apiFetch<{ execution_id: string }>(`/api/v1/agents/${agentId}/execute`, {
        method: "POST",
        json: { message },
      });
      setRunExecId(res.execution_id);
      // Poll for result
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        if (attempts > 30) {
          clearInterval(poll);
          setRunError("Execution timed out. Check logs.");
          setRunning(false);
          return;
        }
        try {
          const exec = await apiFetch<{ status: string; answer: string | null }>(
            `/api/v1/executions/${res.execution_id}`,
          );
          if (exec.status === "completed") {
            clearInterval(poll);
            setRunResult(exec.answer ?? "No answer returned.");
            setRunning(false);
          } else if (exec.status === "failed") {
            clearInterval(poll);
            setRunError("Execution failed.");
            setRunning(false);
          }
        } catch {
          // ignore transient errors
        }
      }, 3000);
    } catch (e) {
      setRunError(String(e));
      setRunning(false);
    }
  }

  const filtered = kgSearch
    ? kgNodes.filter(
        (n) =>
          n.label.toLowerCase().includes(kgSearch.toLowerCase()) ||
          (n.summary ?? "").toLowerCase().includes(kgSearch.toLowerCase()),
      )
    : kgNodes;

  const activeCount = selectedNodeIds.size > 0 ? selectedNodeIds.size : canvasItems.length;

  return (
    <div className="flex h-[calc(100vh-4rem)] gap-0 overflow-hidden">
      {/* Left: KG browser */}
      <div className="flex w-64 shrink-0 flex-col border-r border-flow-800 bg-flow-950">
        <div className="border-b border-flow-800 p-3">
          <h2 className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-wider text-flow-500">
            Knowledge Graph
          </h2>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3 w-3 -translate-y-1/2 text-flow-600" />
            <Input
              value={kgSearch}
              onChange={(e) => setKgSearch(e.target.value)}
              placeholder="Search nodes…"
              className="h-7 pl-7 font-mono text-[10px]"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {loadingKg ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-4 w-4 animate-spin text-flow-600" />
            </div>
          ) : filtered.length === 0 ? (
            <p className="py-6 text-center font-mono text-[10px] text-flow-700">
              {kgSearch ? "No matches" : "No KG nodes yet"}
            </p>
          ) : (
            filtered.slice(0, 200).map((n) => (
              <KGNodeItem key={n.id} node={n} onAdd={addNodeToCanvas} />
            ))
          )}
        </div>
      </div>

      {/* Center: canvas */}
      <div
        ref={reactFlowWrapper}
        className="relative flex-1"
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
      >
        {canvasItems.length === 0 && (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-3 z-10">
            <Sparkles className="h-8 w-8 text-flow-800" />
            <p className="font-mono text-xs text-flow-700">
              Drag nodes from the sidebar or click <Plus className="inline h-3 w-3" /> to add
            </p>
          </div>
        )}
        <ReactFlow
          nodes={rfNodes}
          edges={rfEdges}
          onNodesChange={onRfNodesChange}
          onEdgesChange={onRfEdgesChange}
          onSelectionChange={onSelectionChange}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          minZoom={0.2}
          maxZoom={2}
          nodesConnectable={false}
          deleteKeyCode={null}
        >
          <Background gap={24} size={1} color="rgba(255,255,255,0.03)" />
          <Controls showInteractive={false} />
          <MiniMap
            className="!bg-flow-900/90 !border-flow-800"
            maskColor="rgba(0,0,0,0.3)"
            nodeColor={(n) => nodeTypeColor(
              canvasItems.find((c) => c.kgId === n.id)?.node_type ?? "",
            )}
          />
        </ReactFlow>

        {/* Canvas toolbar */}
        {canvasItems.length > 0 && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2 rounded-[10px] border border-flow-700 bg-flow-900/95 px-3 py-2 shadow-xl backdrop-blur-sm">
            <span className="font-mono text-[10px] text-flow-500">
              {canvasItems.length} nodes
              {selectedNodeIds.size > 0 && ` · ${selectedNodeIds.size} selected`}
            </span>
            <div className="h-3 w-px bg-flow-700" />
            <button
              onClick={clearCanvas}
              className="flex h-6 items-center gap-1 rounded-[5px] px-2 font-mono text-[10px] text-flow-500 hover:bg-flow-800 hover:text-flow-200 transition-colors"
            >
              <Trash2 className="h-3 w-3" /> Clear
            </button>
          </div>
        )}
      </div>

      {/* Right: agent + run panel */}
      <div className="flex w-64 shrink-0 flex-col border-l border-flow-800 bg-flow-950">
        <div className="border-b border-flow-800 p-3">
          <h2 className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-wider text-flow-500">
            Run Agent
          </h2>
          <div className="space-y-2">
            <Select value={agentId} onValueChange={(v) => v && setAgentId(v)}>
              <SelectTrigger className="h-8 w-full font-mono text-xs">
                <Bot className="mr-1.5 h-3 w-3 shrink-0 text-flow-500" />
                <SelectValue placeholder="Pick agent…" />
              </SelectTrigger>
              <SelectContent>
                {agents.map((a) => (
                  <SelectItem key={a.id} value={a.id} className="font-mono text-xs">
                    {a.name || a.template}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button
              onClick={() => void runOnCluster()}
              disabled={running || canvasItems.length === 0 || !agentId}
              className="w-full gap-1.5 font-mono text-xs"
              size="sm"
            >
              {running ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Running…
                </>
              ) : (
                <>
                  <Sparkles className="h-3.5 w-3.5" />
                  Run on {activeCount > 0 ? `${activeCount} node${activeCount > 1 ? "s" : ""}` : "canvas"}
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Result */}
        <div className="flex-1 overflow-y-auto p-3">
          {runExecId && (
            <a
              href={`/executions/${runExecId}`}
              className="mb-3 flex items-center gap-1 font-mono text-[10px] text-flow-500 hover:text-flow-200 transition-colors"
            >
              <Activity className="h-3 w-3" />
              View replay
            </a>
          )}
          {runError && (
            <div className="rounded-[6px] border border-destructive/30 bg-destructive/10 p-3">
              <div className="mb-1 flex items-center gap-1 font-mono text-[10px] font-semibold text-destructive">
                <AlertCircle className="h-3 w-3" /> Error
              </div>
              <p className="text-[10px] text-destructive/80">{runError}</p>
            </div>
          )}
          {runResult && (
            <div className="rounded-[6px] border border-emerald-500/20 bg-emerald-500/5 p-3">
              <p className="mb-1.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-emerald-500">
                Result
              </p>
              <p className="text-[11px] leading-relaxed text-flow-300">{runResult}</p>
            </div>
          )}
          {!runResult && !runError && !running && canvasItems.length === 0 && (
            <p className="mt-4 text-center font-mono text-[10px] text-flow-700">
              Add nodes to canvas, then run an agent to synthesize insights.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
