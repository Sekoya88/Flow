"use client";

import { useCallback, useEffect, useState } from "react";
import { Network } from "lucide-react";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { KnowledgeGraphCanvas, type KGEdge, type KGNode } from "@/components/kg/KnowledgeGraphCanvas";
import { GraphQueryPanel } from "@/components/kg/GraphQueryPanel";
import { apiFetch } from "@/lib/api";
import { useStore } from "@/lib/store";

export default function GraphPage() {
  const workspaces = useStore((s) => s.workspaces);
  const workspaceId = workspaces[0]?.id ?? null;

  const [nodes, setNodes] = useState<KGNode[]>([]);
  const [edges, setEdges] = useState<KGEdge[]>([]);
  const [loading, setLoading] = useState(true);
  const [highlightedIds, setHighlightedIds] = useState<Set<string>>(new Set());
  const [pathLabels, setPathLabels] = useState<string[]>([]);

  useEffect(() => {
    if (!workspaceId) return;
    apiFetch<{ nodes: KGNode[]; edges: KGEdge[]; cluster_count: number }>(
      `/api/v1/kg/graph?workspace_id=${workspaceId}`,
    )
      .then((data) => {
        setNodes(data.nodes ?? []);
        setEdges(data.edges ?? []);
      })
      .catch(console.warn)
      .finally(() => setLoading(false));
  }, [workspaceId]);

  const handleHighlight = useCallback((ids: string[]) => {
    setHighlightedIds(new Set(ids));
  }, []);

  const handlePathHighlight = useCallback((labels: string[]) => {
    setPathLabels(labels);
  }, []);

  if (!workspaceId) return null;

  return (
    <div className="flex h-[calc(100vh-48px)] flex-col overflow-hidden">
      <FlowPageHeader
        title="Knowledge Graph"
        description={loading ? "Loading…" : `${nodes.length} nodes · ${edges.length} edges`}
      />
      <div className="flex flex-1 overflow-hidden">
        {loading ? (
          <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
            Loading graph…
          </div>
        ) : nodes.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-muted-foreground">
            <Network className="h-10 w-10 opacity-20" />
            <p className="text-sm">No notes yet. Import your Obsidian vault to get started.</p>
          </div>
        ) : (
          <KnowledgeGraphCanvas
            nodes={nodes}
            edges={edges}
            highlightedNodeIds={highlightedIds}
            highlightedPath={pathLabels}
            className="flex-1"
          />
        )}
        <GraphQueryPanel
          workspaceId={workspaceId}
          onHighlight={handleHighlight}
          onPathHighlight={handlePathHighlight}
        />
      </div>
    </div>
  );
}
