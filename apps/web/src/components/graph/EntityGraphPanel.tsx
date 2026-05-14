'use client'
import { useCallback, useEffect, useMemo } from 'react'
import {
  ReactFlow,
  Background,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useEntityGraph } from '@/lib/graph/useEntityGraph'
import { NODE_COLORS } from '@/lib/graph/graphColors'
import type { NodeType } from '@/lib/graph/types'
import type { KGNode } from '@/lib/graph/types'
import { useRouter } from 'next/navigation'

const ENTITY_PAGE: Partial<Record<NodeType, string>> = {
  agent:          '/agents',
  skill:          '/skills',
  genome_version: '/agents',
}

interface EntityGraphPanelProps {
  workspaceId: string
  nodeType: NodeType
  refId: string
  onClose: () => void
}

function buildLayout(
  rootNode: KGNode,
  neighbours: KGNode[],
  edges: Array<{ id: string; source_id: string; target_id: string; edge_type: string }>,
): { nodes: Node[]; edges: Edge[] } {
  const GAP = 130
  const rootX = Math.max(200, (neighbours.length * GAP) / 2)

  const flowNodes: Node[] = [
    {
      id: rootNode.id,
      position: { x: rootX, y: 40 },
      data: {
        label: rootNode.label,
        nodeType: rootNode.node_type,
        refId: rootNode.ref_id,
      },
      style: {
        background: '#1e293b',
        border: `2px solid ${NODE_COLORS[rootNode.node_type] ?? '#6366f1'}`,
        borderRadius: 6,
        color: NODE_COLORS[rootNode.node_type] ?? '#6366f1',
        fontSize: 11,
        padding: '4px 10px',
      },
    },
    ...neighbours.map((n, i) => ({
      id: n.id,
      position: { x: i * GAP + 20, y: 160 },
      data: { label: n.label, nodeType: n.node_type, refId: n.ref_id },
      style: {
        background: '#1e293b',
        border: `1.5px solid ${NODE_COLORS[n.node_type] ?? '#334155'}`,
        borderRadius: 4,
        color: NODE_COLORS[n.node_type] ?? '#94a3b8',
        fontSize: 10,
        padding: '3px 8px',
      },
    })),
  ]

  const flowEdges: Edge[] = edges.map(e => ({
    id: e.id,
    source: e.source_id,
    target: e.target_id,
    label: e.edge_type,
    labelStyle: { fontSize: 9, fill: '#475569' },
    style: { stroke: '#334155', strokeWidth: 1 },
    animated: false,
  }))

  return { nodes: flowNodes, edges: flowEdges }
}

export function EntityGraphPanel({
  workspaceId,
  nodeType,
  refId,
  onClose,
}: EntityGraphPanelProps) {
  const router = useRouter()
  const { data, loading, error } = useEntityGraph({
    workspaceId,
    nodeType,
    refId,
    enabled: Boolean(workspaceId && refId),
  })

  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    if (!data) return { nodes: [], edges: [] }
    return buildLayout(
      data.node,
      data.neighbours,
      data.edges,
    )
  }, [data])

  const [nodes, setNodes] = useNodesState(initialNodes)
  const [edges, setEdges] = useEdgesState(initialEdges)

  useEffect(() => {
    setNodes(initialNodes)
    setEdges(initialEdges)
  }, [initialNodes, initialEdges, setNodes, setEdges])

  const onNodeDoubleClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const nt = node.data?.nodeType
      const rid = node.data?.refId as string | null
      if (typeof nt !== 'string') return
      const base = ENTITY_PAGE[nt as NodeType]
      if (base && rid) router.push(`${base}/${rid}`)
    },
    [router],
  )

  return (
    <div
      className="fixed inset-y-0 right-0 w-80 bg-slate-900 border-l border-slate-700
                 flex flex-col shadow-2xl z-40"
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-700">
        <div
          className="w-2.5 h-2.5 rounded-full"
          style={{ background: NODE_COLORS[nodeType] ?? '#6366f1' }}
        />
        <span className="text-sm font-semibold text-slate-100 truncate">
          Local graph
        </span>
        <button
          onClick={onClose}
          className="ml-auto text-slate-500 hover:text-slate-300 text-sm"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-slate-500 text-sm">Loading…</span>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-red-400 text-xs px-4 text-center">{error}</span>
          </div>
        )}
        {!loading && !error && data && (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodeDoubleClick={onNodeDoubleClick}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            nodesDraggable={false}
            zoomOnScroll={false}
            panOnDrag
          >
            <Background color="#1e293b" gap={20} />
          </ReactFlow>
        )}
      </div>

      <div className="flex gap-2 px-4 py-3 border-t border-slate-700">
        <a
          href={`/graph?focus=${refId}`}
          className="flex-1 text-center bg-slate-800 border border-slate-600
                     text-slate-300 text-xs py-1.5 rounded hover:bg-slate-700"
        >
          Expand in graph ↗
        </a>
        <a
          href="/graph"
          className="flex-1 text-center bg-indigo-600 text-white text-xs py-1.5 rounded
                     hover:bg-indigo-500"
        >
          Full graph
        </a>
      </div>
    </div>
  )
}
