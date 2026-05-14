export type NodeType =
  | 'agent'
  | 'skill'
  | 'genome_version'
  | 'system_prompt'
  | 'execution'
  | 'sub_agent'
  | 'tool_call'
  // legacy document types
  | 'note'
  | 'concept'
  | 'topic'
  | 'query'
  | 'trace'
  | 'prompt'
  | 'metacog'

export interface KGNode {
  id: string
  workspace_id?: string
  node_type: NodeType
  ref_id: string | null
  ref_type: string | null
  label: string
  metadata: Record<string, unknown>
  pos_x: number | null
  pos_y: number | null
}

export interface KGEdge {
  id: string
  source_id: string
  target_id: string
  edge_type: string
  weight: number | null
}

export interface WorkspaceGraph {
  nodes: KGNode[]
  edges: KGEdge[]
}

export interface EntityGraph {
  node: KGNode
  neighbours: KGNode[]
  edges: KGEdge[]
}

export const ENTITY_NODE_TYPES: NodeType[] = [
  'agent',
  'skill',
  'genome_version',
  'system_prompt',
  'execution',
  'sub_agent',
  'tool_call',
]

export const DOCUMENT_NODE_TYPES: NodeType[] = [
  'note', 'concept', 'topic', 'query', 'trace', 'prompt', 'metacog',
]
