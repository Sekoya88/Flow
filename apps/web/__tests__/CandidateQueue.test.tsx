import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import React from 'react'
import { CandidateQueue } from '@/components/preferences/CandidateQueue'
import type { Preference } from '@/lib/usePreferences'

vi.mock('@/components/preferences/PreferenceRow', () => ({
  PreferenceRow: ({ pref }: { pref: Preference }) => (
    <div data-testid="preference-row">{pref.value}</div>
  ),
}))

const makeCandidate = (id: string, value: string): Preference => ({
  id,
  class: 'tooling',
  value,
  score: 0.5,
  status: 'candidate',
  pinned: false,
  agent_id: null,
  last_reinforced_at: new Date().toISOString(),
  created_at: new Date().toISOString(),
})

const twoCandidates = [makeCandidate('c1', 'uses TypeScript'), makeCandidate('c2', 'prefers dark mode')]

describe('CandidateQueue', () => {
  it('renders pending review heading', () => {
    render(
      <CandidateQueue
        candidates={twoCandidates}
        onPatch={vi.fn()}
        onBulkPromote={vi.fn()}
        onBulkDismiss={vi.fn()}
      />
    )
    expect(screen.getByText(/pending review/i)).toBeInTheDocument()
  })

  it('shows candidate count', () => {
    render(
      <CandidateQueue
        candidates={twoCandidates}
        onPatch={vi.fn()}
        onBulkPromote={vi.fn()}
        onBulkDismiss={vi.fn()}
      />
    )
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('calls onBulkPromote when Promote all clicked', () => {
    const onBulkPromote = vi.fn()
    render(
      <CandidateQueue
        candidates={twoCandidates}
        onPatch={vi.fn()}
        onBulkPromote={onBulkPromote}
        onBulkDismiss={vi.fn()}
      />
    )
    fireEvent.click(screen.getByText(/promote all/i))
    expect(onBulkPromote).toHaveBeenCalledOnce()
  })

  it('calls onBulkDismiss when Dismiss all clicked', () => {
    const onBulkDismiss = vi.fn()
    render(
      <CandidateQueue
        candidates={twoCandidates}
        onPatch={vi.fn()}
        onBulkPromote={vi.fn()}
        onBulkDismiss={onBulkDismiss}
      />
    )
    fireEvent.click(screen.getByText(/dismiss all/i))
    expect(onBulkDismiss).toHaveBeenCalledOnce()
  })

  it('renders each candidate row', () => {
    render(
      <CandidateQueue
        candidates={twoCandidates}
        onPatch={vi.fn()}
        onBulkPromote={vi.fn()}
        onBulkDismiss={vi.fn()}
      />
    )
    expect(screen.getByText('uses TypeScript')).toBeInTheDocument()
    expect(screen.getByText('prefers dark mode')).toBeInTheDocument()
    expect(screen.getAllByTestId('preference-row')).toHaveLength(2)
  })

  it('disables bulk buttons when no candidates', () => {
    render(
      <CandidateQueue
        candidates={[]}
        onPatch={vi.fn()}
        onBulkPromote={vi.fn()}
        onBulkDismiss={vi.fn()}
      />
    )
    expect(screen.getByText(/promote all/i)).toBeDisabled()
    expect(screen.getByText(/dismiss all/i)).toBeDisabled()
  })

  it('shows empty message when no candidates', () => {
    render(
      <CandidateQueue
        candidates={[]}
        onPatch={vi.fn()}
        onBulkPromote={vi.fn()}
        onBulkDismiss={vi.fn()}
      />
    )
    expect(screen.getByText(/no candidates pending review/i)).toBeInTheDocument()
  })
})
