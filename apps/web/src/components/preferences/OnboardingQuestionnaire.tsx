'use client'

import React, { useState } from 'react'
import { ArrowRight, AlertCircle, Loader2, Sparkles } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from '@/components/ui/card'

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
  const progress = ((step + 1) / QUESTIONS.length) * 100

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

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      handleNext()
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-10 animate-fade-in">
      <Card
        role="dialog"
        aria-modal="true"
        className="surface-glass-heavy border-flow-brand/20 shadow-xl shadow-flow-brand/10"
      >
        <CardHeader className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-3.5 w-3.5 text-flow-brand" />
              <span className="font-mono text-[11px] uppercase tracking-[0.22em] text-flow-brand/80">
                Step {step + 1} of {QUESTIONS.length}
              </span>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onDismiss}
              disabled={submitting}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Skip setup
            </Button>
          </div>
          <div
            className="h-1 w-full overflow-hidden rounded-full bg-muted/50"
            role="progressbar"
            aria-valuenow={Math.round(progress)}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="h-full rounded-full bg-flow-brand transition-all duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
        </CardHeader>

        <CardContent key={step} className="space-y-5 animate-slide-up">
          <div className="space-y-2">
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-2xl font-semibold leading-tight tracking-tight text-foreground">
                {question.text}
              </h2>
              {isOptional && (
                <Badge
                  variant="secondary"
                  className="shrink-0 font-mono text-[10px] uppercase tracking-wider"
                >
                  Optional
                </Badge>
              )}
            </div>
            <p className="text-xs font-mono text-muted-foreground/70">
              {question.class}
            </p>
          </div>

          <Textarea
            value={currentInput}
            onChange={(e) => setCurrentInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={submitting}
            autoFocus
            placeholder={isOptional ? 'Skip or type your answer…' : 'Type your answer…'}
            className="min-h-[88px] resize-none rounded-xl border-border/60 bg-card/60 text-sm focus-visible:border-flow-brand/50 focus-visible:ring-flow-brand/30"
          />

          {error && (
            <p
              role="alert"
              className="flex items-center gap-1.5 text-sm text-destructive"
            >
              <AlertCircle className="h-3.5 w-3.5" />
              {error}
            </p>
          )}

          <p className="text-[11px] font-mono text-muted-foreground/50">
            ⌘ / Ctrl + Enter to continue
          </p>
        </CardContent>

        <CardFooter className="flex items-center justify-end gap-2 pt-2">
          {isOptional && (
            <Button
              type="button"
              variant="outline"
              onClick={handleSkip}
              disabled={submitting}
            >
              Skip
            </Button>
          )}
          <Button
            type="button"
            onClick={handleNext}
            disabled={submitting}
            className="gap-1.5 bg-flow-brand text-white shadow-md shadow-flow-brand/20 hover:bg-flow-brand/90"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Saving…
              </>
            ) : (
              <>
                {isLast ? 'Submit' : 'Next'}
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}
