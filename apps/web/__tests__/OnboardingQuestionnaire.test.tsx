import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
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

function fillAndAdvance(answer = 'test answer') {
  const input = screen.getByRole('textbox')
  fireEvent.change(input, { target: { value: answer } })
  fireEvent.click(screen.getByRole('button', { name: /next/i }))
}

describe('OnboardingQuestionnaire', () => {
  it('renders first question', () => {
    render(<OnboardingQuestionnaire {...defaultProps} />)
    expect(
      screen.getByText('What programming languages do you use most?')
    ).toBeInTheDocument()
    expect(screen.getByText('Step 1 of 7')).toBeInTheDocument()
  })

  it('advances to next step on Next click', () => {
    render(<OnboardingQuestionnaire {...defaultProps} />)
    fillAndAdvance('Python, TypeScript')
    expect(
      screen.getByText("What's your main professional domain?")
    ).toBeInTheDocument()
    expect(screen.getByText('Step 2 of 7')).toBeInTheDocument()
  })

  it('shows skip button for optional questions', () => {
    render(<OnboardingQuestionnaire {...defaultProps} />)
    // Steps 0-3 are required; step 4 is optional
    fillAndAdvance('Python')
    fillAndAdvance('Software Engineering')
    fillAndAdvance('Bullet points')
    fillAndAdvance('Learning Rust')
    // Now at step 4 (optional)
    expect(
      screen.getByText('Are there tools, patterns, or suggestions you never want to see?')
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^skip$/i })).toBeInTheDocument()
  })

  it('skipping optional question advances without submitting answer', async () => {
    const onComplete = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        text: async () => JSON.stringify({ created: 3 }),
      })
    )

    render(<OnboardingQuestionnaire workspaceId="ws-123" onComplete={onComplete} onDismiss={vi.fn()} />)

    fillAndAdvance('Python')
    fillAndAdvance('Software Engineering')
    fillAndAdvance('Bullet points')
    fillAndAdvance('Learning Rust')

    // Step 4 is optional — click Skip
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))

    // Now at step 5 (optional)
    expect(
      screen.getByText('Any tech stack preferences we should know about?')
    ).toBeInTheDocument()

    // Fill step 5 and skip step 6, then submit
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))
    // Step 6
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))

    await waitFor(() => {
      const fetchMock = (global.fetch as ReturnType<typeof vi.fn>)
      expect(fetchMock).toHaveBeenCalledOnce()
      const body = JSON.parse(fetchMock.mock.calls[0][1].body)
      // The skipped step 4 should not appear in answers
      const classes = body.answers.map((a: { class: string }) => a.class)
      // step 4 class is 'veto', should not be present
      expect(classes).not.toContain('veto')
    })
  })

  it('submit calls onboarding endpoint with correct payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => JSON.stringify({ created: 4 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<OnboardingQuestionnaire workspaceId="ws-456" onComplete={vi.fn()} onDismiss={vi.fn()} />)

    fillAndAdvance('Python, TypeScript')
    fillAndAdvance('Software Engineering')
    fillAndAdvance('Bullet points')
    fillAndAdvance('Learning Rust')

    // Steps 4, 5, 6 are optional — skip all
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))
    // Last step — submit via Skip (optional)
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledOnce()
      const [url, options] = fetchMock.mock.calls[0]
      expect(url).toContain('/api/v1/preferences/onboarding')
      expect(options.method).toBe('POST')
      const body = JSON.parse(options.body)
      expect(body.workspace_id).toBe('ws-456')
      expect(body.answers).toEqual([
        { class: 'tooling', value: 'Python, TypeScript' },
        { class: 'domain', value: 'Software Engineering' },
        { class: 'style', value: 'Bullet points' },
        { class: 'goal', value: 'Learning Rust' },
      ])
    })
  })

  it('calls onComplete with created count on success', async () => {
    const onComplete = vi.fn()
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        text: async () => JSON.stringify({ created: 5 }),
      })
    )

    render(<OnboardingQuestionnaire workspaceId="ws-123" onComplete={onComplete} onDismiss={vi.fn()} />)

    fillAndAdvance('Python')
    fillAndAdvance('Engineering')
    fillAndAdvance('Concise')
    fillAndAdvance('Build a compiler')

    // Skip all optional steps
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))

    await waitFor(() => {
      expect(onComplete).toHaveBeenCalledWith(5)
    })
  })

  it('shows error on fetch failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new Error('Network error'))
    )

    render(<OnboardingQuestionnaire {...defaultProps} />)

    fillAndAdvance('Python')
    fillAndAdvance('Engineering')
    fillAndAdvance('Concise')
    fillAndAdvance('Build a compiler')

    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))

    await waitFor(() => {
      expect(
        screen.getByText('Something went wrong. Please try again.')
      ).toBeInTheDocument()
    })
  })

  it('shows error on server error response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 500, text: async () => 'Server error' })
    )
    render(<OnboardingQuestionnaire {...defaultProps} />)
    fillAndAdvance('Python')
    fillAndAdvance('Engineering')
    fillAndAdvance('Concise')
    fillAndAdvance('Build a compiler')
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))
    fireEvent.click(screen.getByRole('button', { name: /^skip$/i }))
    await waitFor(() => {
      expect(screen.getByText('Something went wrong. Please try again.')).toBeInTheDocument()
    })
  })

  it('shows error when required field is empty', () => {
    render(<OnboardingQuestionnaire {...defaultProps} />)
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText('This field is required.')).toBeInTheDocument()
    expect(screen.getByText('Step 1 of 7')).toBeInTheDocument()
  })

  it('skip setup calls onDismiss', () => {
    const onDismiss = vi.fn()
    render(
      <OnboardingQuestionnaire
        workspaceId="ws-123"
        onComplete={vi.fn()}
        onDismiss={onDismiss}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /skip setup/i }))
    expect(onDismiss).toHaveBeenCalledOnce()
  })
})
