import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import React from 'react'
import { OnboardingQuestionnaire } from '@/components/preferences/OnboardingQuestionnaire'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

const defaultProps = {
  workspaceId: 'ws-123',
  onComplete: vi.fn(),
  onDismiss: vi.fn(),
}

describe('OnboardingQuestionnaire — chip suggestions', () => {
  it('renders suggestion chips for the first question', () => {
    render(<OnboardingQuestionnaire {...defaultProps} />)
    expect(screen.getByRole('button', { name: /^Python$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^TypeScript$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Go$/i })).toBeInTheDocument()
  })

  it('toggles chip selection visually via aria-pressed', () => {
    render(<OnboardingQuestionnaire {...defaultProps} />)
    const chip = screen.getByRole('button', { name: /^Python$/i })
    expect(chip.getAttribute('aria-pressed')).toBe('false')
    fireEvent.click(chip)
    expect(chip.getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(chip)
    expect(chip.getAttribute('aria-pressed')).toBe('false')
  })

  it('advances on Next when at least one chip is selected (no free text)', () => {
    render(<OnboardingQuestionnaire {...defaultProps} />)
    fireEvent.click(screen.getByRole('button', { name: /^Python$/i }))
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(
      screen.getByText("What's your main professional domain?")
    ).toBeInTheDocument()
  })

  it('sends one payload entry per selected chip with same class', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => JSON.stringify({ created: 6 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<OnboardingQuestionnaire workspaceId="ws-xyz" onComplete={vi.fn()} onDismiss={vi.fn()} />)

    // Q1: pick 2 language chips
    fireEvent.click(screen.getByRole('button', { name: /^Python$/i }))
    fireEvent.click(screen.getByRole('button', { name: /^TypeScript$/i }))
    fireEvent.click(screen.getByRole('button', { name: /next/i }))

    // Q2: pick 1 domain chip
    fireEvent.click(screen.getByRole('button', { name: /^Backend$/i }))
    fireEvent.click(screen.getByRole('button', { name: /next/i }))

    // Q3 style
    fireEvent.click(screen.getByRole('button', { name: /^Bullet points$/i }))
    fireEvent.click(screen.getByRole('button', { name: /next/i }))

    // Q4 goal
    fireEvent.click(screen.getByRole('button', { name: /^Databases$/i }))
    fireEvent.click(screen.getByRole('button', { name: /next/i }))

    // Q5/Q6/Q7 — skip optional
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledOnce()
      const body = JSON.parse(fetchMock.mock.calls[0][1].body)
      expect(body.workspace_id).toBe('ws-xyz')

      const toolingEntries = body.answers.filter((a: { class: string }) => a.class === 'tooling')
      expect(toolingEntries.length).toBe(2)
      expect(toolingEntries.map((a: { value: string }) => a.value).sort()).toEqual(
        ['Python', 'TypeScript'],
      )

      const domainEntries = body.answers.filter((a: { class: string }) => a.class === 'domain')
      expect(domainEntries.length).toBe(1)
      expect(domainEntries[0].value).toBe('Backend')
    })
  })

  it('combines chip selection with free text into separate entries', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => JSON.stringify({ created: 5 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<OnboardingQuestionnaire {...defaultProps} />)

    // Q1: chip + free text
    fireEvent.click(screen.getByRole('button', { name: /^Python$/i }))
    const textbox = screen.getByRole('textbox')
    fireEvent.change(textbox, { target: { value: 'Elixir-curious' } })
    fireEvent.click(screen.getByRole('button', { name: /next/i }))

    // walk the rest with free text only
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'eng' } })
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'bullets' } })
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'compiler' } })
    fireEvent.click(screen.getByRole('button', { name: /next/i }))

    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledOnce()
      const body = JSON.parse(fetchMock.mock.calls[0][1].body)
      const toolingValues = body.answers
        .filter((a: { class: string }) => a.class === 'tooling')
        .map((a: { value: string }) => a.value)
        .sort()
      expect(toolingValues).toEqual(['Elixir-curious', 'Python'])
    })
  })

  it('required question errors when nothing is chip-selected and no free text', () => {
    render(<OnboardingQuestionnaire {...defaultProps} />)
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText('This field is required.')).toBeInTheDocument()
    // Still on step 1
    expect(screen.getByText('Step 1 of 7')).toBeInTheDocument()
  })
})
