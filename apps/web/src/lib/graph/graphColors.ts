import type { NodeType } from './types'

export const NODE_COLORS: Record<NodeType, string> = {
  agent:          '#6366f1',
  skill:          '#22d3ee',
  genome_version: '#f59e0b',
  system_prompt:  '#a78bfa',
  execution:      '#10b981',
  sub_agent:      '#818cf8',
  tool_call:      '#f97316',
  note:           '#64748b',
  concept:        '#64748b',
  topic:          '#64748b',
  query:          '#64748b',
  trace:          '#64748b',
  prompt:         '#64748b',
  metacog:        '#64748b',
}

export const NODE_SIZE: Record<NodeType, number> = {
  agent:          12,
  skill:          8,
  genome_version: 7,
  system_prompt:  6,
  execution:      5,
  sub_agent:      9,
  tool_call:      5,
  note:           4,
  concept:        4,
  topic:          4,
  query:          4,
  trace:          4,
  prompt:         4,
  metacog:        4,
}
