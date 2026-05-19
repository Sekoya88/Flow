import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import React from 'react'
import { PreferenceSection } from '@/components/preferences/PreferenceSection'
import type { Preference } from '@/lib/usePreferences'

const mockPref: Preference = {
  id: 'pref-1',
  class: 'tooling',
  value: 'uses Python',
  score: 0.9,
  status: 'active',
  pinned: false,
  agent_id: null,
  last_reinforced_at: new Date().toISOString(),
  created_at: new Date().toISOString(),
}

describe('PreferenceSection', () => {
  it('renders section title', () => {
    render(
      <PreferenceSection
        cls="tooling"
        prefs={[mockPref]}
        onPatch={vi.fn()}
        onAdd={vi.fn()}
      />
    )
    expect(screen.getAllByText(/tooling/i).length).toBeGreaterThan(0)
  })

  it('renders preference value', () => {
    render(
      <PreferenceSection
        cls="tooling"
        prefs={[mockPref]}
        onPatch={vi.fn()}
        onAdd={vi.fn()}
      />
    )
    expect(screen.getByText('uses Python')).toBeInTheDocument()
  })

  it('calls onPatch with promote when promote button clicked', () => {
    const onPatch = vi.fn()
    render(
      <PreferenceSection
        cls="tooling"
        prefs={[{ ...mockPref, status: 'candidate' }]}
        onPatch={onPatch}
        onAdd={vi.fn()}
      />
    )
    fireEvent.click(screen.getByTitle(/promote/i))
    expect(onPatch).toHaveBeenCalledWith('pref-1', 'promote')
  })

  it('calls onPatch with forget when forget button clicked', () => {
    const onPatch = vi.fn()
    render(
      <PreferenceSection
        cls="tooling"
        prefs={[mockPref]}
        onPatch={onPatch}
        onAdd={vi.fn()}
      />
    )
    fireEvent.click(screen.getByTitle(/forget/i))
    expect(onPatch).toHaveBeenCalledWith('pref-1', 'forget')
  })

  it('shows provisional badge text "learning" for provisional status', () => {
    const provisionalPref = { ...mockPref, status: 'provisional' as const }
    render(
      <PreferenceSection
        cls="tooling"
        prefs={[provisionalPref]}
        onPatch={vi.fn()}
        onAdd={vi.fn()}
      />
    )
    expect(screen.getByText(/learning/i)).toBeInTheDocument()
  })

  it('shows unpin button title for pinned pref', () => {
    const pinnedPref = { ...mockPref, pinned: true }
    render(
      <PreferenceSection
        cls="tooling"
        prefs={[pinnedPref]}
        onPatch={vi.fn()}
        onAdd={vi.fn()}
      />
    )
    expect(screen.getByTitle(/unpin/i)).toBeInTheDocument()
  })
})
