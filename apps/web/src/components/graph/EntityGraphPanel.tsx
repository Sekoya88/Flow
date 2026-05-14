'use client'
import { useCallback, useEffect, useMemo } from 'react'
import {
  ReactFlow,
  Background,
  useNodesState,
  useEdgesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useEntityGraph } from '@/lib/graph/useEntityGraph'
import { NODE_COLORS } from '@/lib/graph/graphColors'
import { buildEntityLayout } from '@/lib/graph/graphLayouts'
import type { NodeType } from '@/lib/graph/types'
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
    return buildEntityLayout(data.node, data.neighbours, data.edges)
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
