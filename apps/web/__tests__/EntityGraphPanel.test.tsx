import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import React from 'react'

// ── Mocks ──────────────────────────────────────────────────────────────────
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))

vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="react-flow">{children}</div>
  ),
  Background: () => null,
  useNodesState: (init: unknown[]) => [init, vi.fn(), vi.fn()],
  useEdgesState: (init: unknown[]) => [init, vi.fn(), vi.fn()],
}))

// Silence CSS import
vi.mock('@xyflow/react/dist/style.css', () => ({}))

const mockUseEntityGraph = vi.fn()
vi.mock('@/lib/graph/useEntityGraph', () => ({
  useEntityGraph: (...args: unknown[]) => mockUseEntityGraph(...args),
}))

// ── Fixtures ───────────────────────────────────────────────────────────────
const ROOT_NODE = {
  id: 'node-1',
  node_type: 'agent' as const,
  ref_id: 'agent-abc',
  ref_type: 'agent',
  label: 'My Agent',
  metadata: {},
  pos_x: null,
  pos_y: null,
}

const NEIGHBOUR = {
  id: 'node-2',
  node_type: 'skill' as const,
  ref_id: 'skill-xyz',
  ref_type: 'skill',
  label: 'My Skill',
  metadata: {},
  pos_x: null,
  pos_y: null,
}

const EDGE = {
  id: 'edge-1',
  source_id: 'node-1',
  target_id: 'node-2',
  edge_type: 'has_skill',
  weight: null,
}

// ── Tests ──────────────────────────────────────────────────────────────────
import { EntityGraphButton } from '@/components/graph/EntityGraphButton'
import { EntityGraphPanel } from '@/components/graph/EntityGraphPanel'

describe('EntityGraphButton', () => {
  it('should render Graph button', () => {
    render(
      <EntityGraphButton workspaceId="ws-1" nodeType="agent" refId="agent-abc" />,
    )
    expect(screen.getByTitle('Show entity graph')).toBeInTheDocument()
  })

  it('should open panel when button clicked', () => {
    mockUseEntityGraph.mockReturnValue({ data: null, loading: true, error: null })

    render(
      <EntityGraphButton workspaceId="ws-1" nodeType="agent" refId="agent-abc" />,
    )
    expect(screen.queryByText('Local graph')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTitle('Show entity graph'))
    expect(screen.getByText('Local graph')).toBeInTheDocument()
  })

  it('should close panel when close button clicked', () => {
    mockUseEntityGraph.mockReturnValue({ data: null, loading: true, error: null })

    render(
      <EntityGraphButton workspaceId="ws-1" nodeType="agent" refId="agent-abc" />,
    )
    fireEvent.click(screen.getByTitle('Show entity graph'))
    expect(screen.getByText('Local graph')).toBeInTheDocument()

    fireEvent.click(screen.getByText('✕'))
    expect(screen.queryByText('Local graph')).not.toBeInTheDocument()
  })
})

describe('EntityGraphPanel', () => {
  beforeEach(() => {
    mockUseEntityGraph.mockReset()
  })

  it('should display loading state', () => {
    mockUseEntityGraph.mockReturnValue({ data: null, loading: true, error: null })

    render(
      <EntityGraphPanel
        workspaceId="ws-1"
        nodeType="agent"
        refId="agent-abc"
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('should display error state', () => {
    mockUseEntityGraph.mockReturnValue({
      data: null,
      loading: false,
      error: 'Network error',
    })

    render(
      <EntityGraphPanel
        workspaceId="ws-1"
        nodeType="agent"
        refId="agent-abc"
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByText('Network error')).toBeInTheDocument()
  })

  it('should display ReactFlow when data loaded', () => {
    mockUseEntityGraph.mockReturnValue({
      data: { node: ROOT_NODE, neighbours: [NEIGHBOUR], edges: [EDGE] },
      loading: false,
      error: null,
    })

    render(
      <EntityGraphPanel
        workspaceId="ws-1"
        nodeType="agent"
        refId="agent-abc"
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByTestId('react-flow')).toBeInTheDocument()
  })

  it('should have Expand in graph link pointing to /graph?focus=<refId>', () => {
    mockUseEntityGraph.mockReturnValue({
      data: { node: ROOT_NODE, neighbours: [], edges: [] },
      loading: false,
      error: null,
    })

    render(
      <EntityGraphPanel
        workspaceId="ws-1"
        nodeType="agent"
        refId="agent-abc"
        onClose={vi.fn()}
      />,
    )
    const link = screen.getByText(/Expand in graph/i).closest('a')
    expect(link).toHaveAttribute('href', '/graph?focus=agent-abc')
  })

  it('should have Full graph link pointing to /graph', () => {
    mockUseEntityGraph.mockReturnValue({
      data: { node: ROOT_NODE, neighbours: [], edges: [] },
      loading: false,
      error: null,
    })

    render(
      <EntityGraphPanel
        workspaceId="ws-1"
        nodeType="agent"
        refId="agent-abc"
        onClose={vi.fn()}
      />,
    )
    const link = screen.getByText('Full graph').closest('a')
    expect(link).toHaveAttribute('href', '/graph')
  })
})
