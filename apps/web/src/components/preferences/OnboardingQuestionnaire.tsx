'use client'

import React, { useState } from 'react'
import { apiFetch } from '@/lib/api'

interface OnboardingQuestionnaireProps {
  workspaceId: string
  onComplete: (createdCount: number) => void
  onDismiss: () => void
}

interface Question {
  class: string
  text: string
  optional?: boolean
}

const QUESTIONS: Question[] = [
  { class: 'tooling', text: 'What programming languages do you use most?' },
  { class: 'domain', text: "What's your main professional domain?" },
  { class: 'style', text: 'How do you prefer answers formatted?' },
  { class: 'goal', text: 'What are you currently working on or trying to learn?' },
  { class: 'veto', text: 'Are there tools, patterns, or suggestions you never want to see?', optional: true },
  { class: 'tooling', text: 'Any tech stack preferences we should know about?', optional: true },
  { class: 'channel', text: 'How should code examples be presented?', optional: true },
]

export function OnboardingQuestionnaire({
  workspaceId,
  onComplete,
  onDismiss,
}: OnboardingQuestionnaireProps) {
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [currentInput, setCurrentInput] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const question = QUESTIONS[step]
  const isLast = step === QUESTIONS.length - 1
  const isOptional = question.optional === true

  function handleNext() {
    if (!isOptional && !currentInput.trim()) {
      setError('This field is required.')
      return
    }
    setError(null)
    if (currentInput.trim()) {
      setAnswers((prev) => ({ ...prev, [step]: currentInput.trim() }))
    }
    if (isLast) {
      submit({ ...answers, ...(currentInput.trim() ? { [step]: currentInput.trim() } : {}) })
    } else {
      setStep((s) => s + 1)
      setCurrentInput('')
    }
  }

  function handleSkip() {
    if (isLast) {
      submit(answers)
    } else {
      setStep((s) => s + 1)
      setCurrentInput('')
    }
  }

  async function submit(finalAnswers: Record<number, string>) {
    setSubmitting(true)
    setError(null)
    try {
      const payload = {
        workspace_id: workspaceId,
        answers: Object.entries(finalAnswers)
          .filter(([, value]) => value && value.trim())
          .map(([index, value]) => ({
            class: QUESTIONS[Number(index)].class,
            value,
          })),
      }
      const data = await apiFetch<{ created: number }>('/api/v1/preferences/onboarding', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      onComplete(data.created ?? 0)
    } catch {
      setError('Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div role="dialog" aria-modal="true">
      <div>
        <span>Step {step + 1} of 7</span>
        <button type="button" onClick={onDismiss}>
          Skip setup
        </button>
      </div>

      <p>{question.text}</p>

      <input
        type="text"
        value={currentInput}
        onChange={(e) => setCurrentInput(e.target.value)}
        disabled={submitting}
      />

      {error && <p role="alert">{error}</p>}

      <div>
        {isOptional && (
          <button type="button" onClick={handleSkip} disabled={submitting}>
            Skip
          </button>
        )}
        <button type="button" onClick={handleNext} disabled={submitting}>
          {isLast ? 'Submit' : 'Next'}
        </button>
      </div>
    </div>
  )
}
