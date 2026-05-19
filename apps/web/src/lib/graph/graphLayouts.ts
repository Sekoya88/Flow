import type { Node, Edge } from '@xyflow/react'
import { NODE_COLORS } from './graphColors'
import type { KGNode, KGEdge, NodeType } from './types'

const ROW_GAP = 130
const ROOT_Y = 40
const NEIGHBOUR_Y = 160
const NEIGHBOUR_X_OFFSET = 20

export function buildEntityLayout(
  rootNode: KGNode,
  neighbours: KGNode[],
  edges: KGEdge[],
): { nodes: Node[]; edges: Edge[] } {
  const rootX = Math.max(200, (neighbours.length * ROW_GAP) / 2)

  const flowNodes: Node[] = [
    {
      id: rootNode.id,
      position: { x: rootX, y: ROOT_Y },
      data: {
        label: rootNode.label,
        nodeType: rootNode.node_type,
        refId: rootNode.ref_id,
      },
      style: {
        background: '#1e293b',
        border: `2px solid ${NODE_COLORS[rootNode.node_type as NodeType] ?? '#6366f1'}`,
        borderRadius: 6,
        color: NODE_COLORS[rootNode.node_type as NodeType] ?? '#6366f1',
        fontSize: 11,
        padding: '4px 10px',
      },
    },
    ...neighbours.map((n, i) => ({
      id: n.id,
      position: { x: i * ROW_GAP + NEIGHBOUR_X_OFFSET, y: NEIGHBOUR_Y },
      data: { label: n.label, nodeType: n.node_type, refId: n.ref_id },
      style: {
        background: '#1e293b',
        border: `1.5px solid ${NODE_COLORS[n.node_type as NodeType] ?? '#334155'}`,
        borderRadius: 4,
        color: NODE_COLORS[n.node_type as NodeType] ?? '#94a3b8',
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
