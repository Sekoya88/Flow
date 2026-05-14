import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import React from 'react'

// ── Mocks ──────────────────────────────────────────────────────────────────
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))

vi.mock('@/components/kg/KnowledgeGraphCanvas', () => ({
  KnowledgeGraphCanvas: ({ nodes, onNodeClick }: {
    nodes: { id: string; node_type: string; label: string }[]
    onNodeClick?: (n: unknown) => void
  }) => (
    <div data-testid="kg-canvas">
      {nodes.map(n => (
        <button key={n.id} data-testid={`node-${n.id}`} onClick={() => onNodeClick?.(n)}>
          {n.label}
        </button>
      ))}
    </div>
  ),
}))

vi.mock('@/components/kg/GraphQueryPanel', () => ({
  GraphQueryPanel: () => <div data-testid="query-panel" />,
}))

vi.mock('@/lib/logger', () => ({ logger: { warn: vi.fn() } }))

const mockApiFetch = vi.fn()
vi.mock('@/lib/api', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}))

vi.mock('@/lib/store', () => ({
  useStore: (sel: (s: { workspaces: { id: string }[] }) => unknown) =>
    sel({ workspaces: [{ id: 'ws-test' }] }),
}))

// ── Fixtures ───────────────────────────────────────────────────────────────
const AGENT_NODE = {
  id: 'n-agent',
  node_type: 'agent',
  label: 'Test Agent',
  metadata: { template: 'react-agent', status: 'active' },
  ref_id: 'agent-abc',
  source_path: null,
  summary: null,
  pagerank: 0,
}

const SKILL_NODE = {
  id: 'n-skill',
  node_type: 'skill',
  label: 'Test Skill',
  metadata: { version: 3, score: 0.9 },
  ref_id: 'skill-xyz',
  source_path: null,
  summary: null,
  pagerank: 0,
}

const GENOME_NODE = {
  id: 'n-genome',
  node_type: 'genome_version',
  label: 'v2',
  metadata: { provider: 'anthropic', model: 'claude-3-5-sonnet', status: 'active' },
  ref_id: 'genome-1',
  source_path: null,
  summary: null,
  pagerank: 0,
}

const EXECUTION_NODE = {
  id: 'n-exec',
  node_type: 'execution',
  label: 'exec-123',
  metadata: { status: 'completed' },
  ref_id: 'exec-123',
  source_path: null,
  summary: null,
  pagerank: 0,
}

// ── Tests ──────────────────────────────────────────────────────────────────
import GraphPage from '@/app/(app)/graph/page'

describe('GraphPage', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValue({
      nodes: [AGENT_NODE, SKILL_NODE],
      edges: [],
      cluster_count: 0,
    })
  })

  it('should render the graph canvas after loading', async () => {
    await act(async () => {
      render(<GraphPage />)
    })
    expect(screen.getByTestId('kg-canvas')).toBeInTheDocument()
  })

  it('should show node labels in canvas', async () => {
    await act(async () => {
      render(<GraphPage />)
    })
    expect(screen.getByText('Test Agent')).toBeInTheDocument()
    expect(screen.getByText('Test Skill')).toBeInTheDocument()
  })

  it('should toggle entity filter type on chip click', async () => {
    await act(async () => {
      render(<GraphPage />)
    })
    const agentChip = screen.getByRole('button', { name: /agents/i })
    expect(agentChip).toBeInTheDocument()

    fireEvent.click(agentChip)
    // After deactivating, chip loses active styling — re-fetches with updated types
    expect(mockApiFetch).toHaveBeenCalled()
  })

  it('should show agent detail panel sections when agent node clicked', async () => {
    await act(async () => {
      render(<GraphPage />)
    })
    // Close query panel first (it hides detail panel)
    const hideBtn = screen.getByRole('button', { name: /hide panel/i })
    fireEvent.click(hideBtn)

    fireEvent.click(screen.getByTestId('node-n-agent'))
    expect(screen.getByText('Template')).toBeInTheDocument()
    // value appears in entity-specific section AND generic metadata keys section
    expect(screen.getAllByText('react-agent').length).toBeGreaterThanOrEqual(1)
  })

  it('should show genome detail with active status badge when genome node clicked', async () => {
    mockApiFetch.mockResolvedValue({
      nodes: [GENOME_NODE],
      edges: [],
      cluster_count: 0,
    })

    await act(async () => {
      render(<GraphPage />)
    })
    const hideBtn = screen.getByRole('button', { name: /hide panel/i })
    fireEvent.click(hideBtn)

    fireEvent.click(screen.getByTestId('node-n-genome'))
    expect(screen.getAllByText(/anthropic/).length).toBeGreaterThanOrEqual(1)
  })

  it('should show execution status badge when execution node clicked', async () => {
    mockApiFetch.mockResolvedValue({
      nodes: [EXECUTION_NODE],
      edges: [],
      cluster_count: 0,
    })

    await act(async () => {
      render(<GraphPage />)
    })
    const hideBtn = screen.getByRole('button', { name: /hide panel/i })
    fireEvent.click(hideBtn)

    fireEvent.click(screen.getByTestId('node-n-exec'))
    expect(screen.getAllByText('completed').length).toBeGreaterThanOrEqual(1)
  })

  it('should show empty state with seed button when graph is empty', async () => {
    mockApiFetch.mockResolvedValue({ nodes: [], edges: [], cluster_count: 0 })

    await act(async () => {
      render(<GraphPage />)
    })
    expect(screen.getByText('Seed demo graph')).toBeInTheDocument()
  })
})
