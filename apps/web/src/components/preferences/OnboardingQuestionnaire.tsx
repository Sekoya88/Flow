'use client'

import React, { useState } from 'react'
import { ArrowRight, AlertCircle, Check, Loader2, Sparkles } from 'lucide-react'
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
import { cn } from '@/lib/utils'

interface OnboardingQuestionnaireProps {
  workspaceId: string
  onComplete: (createdCount: number) => void
  onDismiss: () => void
}

interface Question {
  class: string
  text: string
  suggestions: string[]
  optional?: boolean
}

const QUESTIONS: Question[] = [
  {
    class: 'tooling',
    text: 'What programming languages do you use most?',
    suggestions: [
      'Python', 'TypeScript', 'JavaScript', 'Go', 'Rust', 'Java',
      'C++', 'Swift', 'Kotlin', 'Ruby', 'Scala', 'Elixir',
    ],
  },
  {
    class: 'domain',
    text: "What's your main professional domain?",
    suggestions: [
      'Software Engineering', 'Data Science', 'ML/AI', 'DevOps',
      'Backend', 'Frontend', 'Full-Stack', 'Product', 'Design', 'QA', 'Security',
    ],
  },
  {
    class: 'style',
    text: 'How do you prefer answers formatted?',
    suggestions: [
      'Bullet points', 'Markdown', 'Plain text', 'With code examples',
      'Step-by-step', 'Concise', 'Verbose', 'Technical', 'With diagrams',
    ],
  },
  {
    class: 'goal',
    text: 'What are you currently working on or trying to learn?',
    suggestions: [
      'Web development', 'Mobile apps', 'APIs / Backends', 'Databases',
      'Cloud architecture', 'ML models', 'DevOps pipelines',
      'Performance', 'Security', 'Mentoring',
    ],
  },
  {
    class: 'veto',
    text: 'Are there tools, patterns, or suggestions you never want to see?',
    suggestions: [
      'Docker', 'Kubernetes', 'GraphQL', 'Microservices', 'Monolith',
      'jQuery', 'PHP', 'Excessive jargon', 'Walls of text', 'Apologetic tone',
    ],
    optional: true,
  },
  {
    class: 'tooling',
    text: 'Any tech stack preferences we should know about?',
    suggestions: [
      'Node.js', 'Next.js', 'Django', 'FastAPI', 'Spring Boot', '.NET',
      'AWS', 'GCP', 'Azure', 'PostgreSQL', 'MongoDB', 'Redis',
    ],
    optional: true,
  },
  {
    class: 'channel',
    text: 'How should code examples be presented?',
    suggestions: [
      'Inline snippets', 'Separate files', 'Syntax-highlighted blocks',
      'With comments', 'With explanations', 'Interactive playground', 'GitHub Gist',
    ],
    optional: true,
  },
]

interface AnswerEntry {
  class: string
  value: string
}

export function OnboardingQuestionnaire({
  workspaceId,
  onComplete,
  onDismiss,
}: OnboardingQuestionnaireProps) {
  const [step, setStep] = useState(0)
  // Chip selections per step index
  const [chipSelections, setChipSelections] = useState<Record<number, Set<string>>>({})
  // Free-text answers per step index
  const [freeTexts, setFreeTexts] = useState<Record<number, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const question = QUESTIONS[step]
  const isLast = step === QUESTIONS.length - 1
  const isOptional = question.optional === true
  const progress = ((step + 1) / QUESTIONS.length) * 100

  const currentChips = chipSelections[step] ?? new Set<string>()
  const currentFreeText = freeTexts[step] ?? ''

  function toggleChip(value: string) {
    setError(null)
    setChipSelections((prev) => {
      const next = new Set(prev[step] ?? new Set<string>())
      if (next.has(value)) {
        next.delete(value)
      } else {
        next.add(value)
      }
      return { ...prev, [step]: next }
    })
  }

  function updateFreeText(value: string) {
    setError(null)
    setFreeTexts((prev) => ({ ...prev, [step]: value }))
  }

  function hasAnswer(stepIdx: number): boolean {
    const chips = chipSelections[stepIdx] ?? new Set<string>()
    const txt = (freeTexts[stepIdx] ?? '').trim()
    return chips.size > 0 || txt.length > 0
  }

  function buildAnswers(): AnswerEntry[] {
    const out: AnswerEntry[] = []
    const seen = new Set<string>()
    for (let i = 0; i < QUESTIONS.length; i++) {
      const q = QUESTIONS[i]
      const chips = chipSelections[i] ?? new Set<string>()
      for (const value of chips) {
        const key = `${q.class}:${value.toLowerCase()}`
        if (!seen.has(key)) {
          seen.add(key)
          out.push({ class: q.class, value })
        }
      }
      const txt = (freeTexts[i] ?? '').trim()
      if (txt) {
        const key = `${q.class}:${txt.toLowerCase()}`
        if (!seen.has(key)) {
          seen.add(key)
          out.push({ class: q.class, value: txt })
        }
      }
    }
    return out
  }

  function handleNext() {
    if (!isOptional && !hasAnswer(step)) {
      setError('This field is required.')
      return
    }
    setError(null)
    if (isLast) {
      void submit()
    } else {
      setStep((s) => s + 1)
    }
  }

  function handleSkip() {
    setError(null)
    if (isLast) {
      void submit()
    } else {
      setStep((s) => s + 1)
    }
  }

  async function submit() {
    setSubmitting(true)
    setError(null)
    try {
      const qs = new URLSearchParams({ workspace_id: workspaceId })
      const data = await apiFetch<{ created: number }>(
        `/api/v1/preferences/onboarding?${qs.toString()}`,
        {
          method: 'POST',
          json: { answers: buildAnswers() },
        },
      )
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

          {/* Chip suggestions */}
          <div className="flex flex-wrap gap-2">
            {question.suggestions.map((suggestion) => {
              const selected = currentChips.has(suggestion)
              return (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => toggleChip(suggestion)}
                  disabled={submitting}
                  className={cn(
                    'group inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-all duration-200',
                    selected
                      ? 'border-flow-brand bg-flow-brand/15 text-flow-brand shadow-sm shadow-flow-brand/10'
                      : 'border-border/50 bg-card/30 text-foreground/70 hover:border-flow-brand/40 hover:bg-flow-brand/[0.04] hover:text-foreground',
                  )}
                  aria-pressed={selected}
                >
                  {selected && <Check className="h-3 w-3" />}
                  {suggestion}
                </button>
              )
            })}
          </div>

          {/* Separator + free text */}
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <div className="h-px flex-1 bg-border/40" />
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground/60">
                or type your own
              </span>
              <div className="h-px flex-1 bg-border/40" />
            </div>
            <Textarea
              value={currentFreeText}
              onChange={(e) => updateFreeText(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={submitting}
              placeholder={
                currentChips.size > 0
                  ? 'Add anything else…'
                  : isOptional
                    ? 'Skip or type your answer…'
                    : 'Type your answer…'
              }
              className="min-h-[72px] resize-none rounded-xl border-border/60 bg-card/60 text-sm focus-visible:border-flow-brand/50 focus-visible:ring-flow-brand/30"
            />
          </div>

          {error && (
            <p
              role="alert"
              className="flex items-center gap-1.5 text-sm text-destructive"
            >
              <AlertCircle className="h-3.5 w-3.5" />
              {error}
            </p>
          )}

          {currentChips.size > 0 && (
            <p className="text-[11px] font-mono text-muted-foreground/50">
              {currentChips.size} selected · ⌘ / Ctrl + Enter to continue
            </p>
          )}
          {currentChips.size === 0 && (
            <p className="text-[11px] font-mono text-muted-foreground/50">
              ⌘ / Ctrl + Enter to continue
            </p>
          )}
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
