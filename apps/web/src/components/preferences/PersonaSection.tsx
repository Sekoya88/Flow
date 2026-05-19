'use client'
import { useEffect, useState } from 'react'
import { AlertTriangle, ArrowRight, Check, ClipboardList, Loader2, RefreshCw, Save, Sparkles, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { usePersona } from '@/lib/usePersona'
import { apiFetch } from '@/lib/api'

const SOUL_QUESTIONS = [
  { id: 'name_role', question: 'What is your name and professional role?' },
  { id: 'passion', question: 'What are you most passionate about or what drives you?' },
  { id: 'style', question: 'How do you prefer to communicate? (tone, level of detail, format)' },
  { id: 'focus', question: 'What are you currently working on or focused on learning?' },
  { id: 'avoid', question: 'What should an AI assistant absolutely NOT do when helping you?' },
] as const

interface PersonaSectionProps {
  workspaceId: string
}

function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime()
  const diffSec = Math.floor((Date.now() - then) / 1000)
  if (diffSec < 60) return 'just now'
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
  return `${Math.floor(diffSec / 86400)}d ago`
}

function derivationChips(derived: Record<string, unknown>): { label: string; tone: 'brand' | 'mute' }[] {
  const chips: { label: string; tone: 'brand' | 'mute' }[] = []
  if (derived.manual) chips.push({ label: 'manual edit', tone: 'brand' })
  if (typeof derived.preferences === 'number' && derived.preferences > 0) {
    chips.push({ label: `${derived.preferences} prefs`, tone: 'mute' })
  }
  if (derived.cv) chips.push({ label: 'résumé', tone: 'mute' })
  if (derived.llm) chips.push({ label: 'LLM synth', tone: 'mute' })
  return chips
}

function SOULQuestionnaire({ workspaceId, onDone, onCancel }: { workspaceId: string; onDone: () => void; onCancel: () => void }) {
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const q = SOUL_QUESTIONS[step]
  const isLast = step === SOUL_QUESTIONS.length - 1
  const progress = ((step + 1) / SOUL_QUESTIONS.length) * 100

  async function submit() {
    setSubmitting(true)
    setError(null)
    try {
      await apiFetch('/api/v1/personas/me/questionnaire', {
        method: 'POST',
        json: {
          workspace_id: workspaceId,
          answers: SOUL_QUESTIONS.map(sq => ({ question: sq.question, answer: answers[sq.id] ?? '' })),
        },
      })
      onDone()
    } catch {
      setError('Something went wrong — please try again.')
      setSubmitting(false)
    }
  }

  function next() {
    if (isLast) { void submit(); return; }
    setStep(s => s + 1)
  }

  return (
    <div className="rounded-lg border border-flow-violet/30 bg-flow-violet/5 p-4 space-y-4 animate-slide-up">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-flow-violet/80">
          Question {step + 1} / {SOUL_QUESTIONS.length}
        </span>
        <button type="button" onClick={onCancel} className="text-muted-foreground hover:text-foreground transition-colors">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="h-0.5 w-full overflow-hidden rounded-full bg-muted/30">
        <div className="h-full rounded-full bg-flow-violet transition-all duration-500" style={{ width: `${progress}%` }} />
      </div>
      <p className="text-sm font-medium text-foreground">{q.question}</p>
      <Textarea
        autoFocus
        value={answers[q.id] ?? ''}
        onChange={e => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
        onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); next() } }}
        placeholder="Your answer… (⌘/Ctrl + Enter to continue)"
        className="min-h-[80px] resize-none border-flow-800 bg-card text-sm focus-visible:border-flow-violet/50"
        disabled={submitting}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="flex items-center justify-end gap-2">
        {step > 0 && (
          <Button type="button" variant="ghost" size="sm" onClick={() => setStep(s => s - 1)} disabled={submitting}>
            Back
          </Button>
        )}
        <Button type="button" size="sm" onClick={next} disabled={submitting} className="gap-1.5 bg-flow-violet text-white hover:bg-flow-violet/90">
          {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : isLast ? <><Check className="h-3.5 w-3.5" />Generate</> : <><ArrowRight className="h-3.5 w-3.5" />Next</>}
        </Button>
      </div>
    </div>
  )
}

export function PersonaSection({ workspaceId }: PersonaSectionProps) {
  const { persona, loading, busy, error, save, regenerate } = usePersona(workspaceId)
  const [draft, setDraft] = useState('')
  const [dirty, setDirty] = useState(false)
  const [showQuestionnaire, setShowQuestionnaire] = useState(false)

  useEffect(() => {
    setDraft(persona?.content_md ?? '')
    setDirty(false)
  }, [persona?.content_md, persona?.version])

  const chips = persona ? derivationChips(persona.derived_from ?? {}) : []
  const charCount = draft.length
  const isStale = Boolean(persona?.derived_from?.stale_since)

  return (
    <section className="flow-card rounded-[6px] border border-flow-800 p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-3.5 w-3.5 text-flow-violet" />
          <h2 className="font-mono text-sm font-semibold uppercase tracking-[0.18em] text-foreground">
            SOUL.md
          </h2>
          {persona && (
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60">
              v{persona.version}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {chips.map(c => (
            <Badge
              key={c.label}
              variant="outline"
              className={
                c.tone === 'brand'
                  ? 'border-flow-violet/40 bg-flow-violet/10 text-flow-violet'
                  : 'border-flow-800 text-muted-foreground'
              }
            >
              {c.label}
            </Badge>
          ))}
        </div>
      </div>

      <p className="mb-3 text-xs text-muted-foreground">
        Identity block injected as the first system message of every agent run.
        Generate from a questionnaire, regenerate from your facets + CV, or edit by hand.
      </p>

      {isStale && (
        <div className="mb-3 flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-600 dark:text-amber-400">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          Your preferences have changed since this was last regenerated — click Regenerate to refresh.
        </div>
      )}

      {showQuestionnaire && (
        <div className="mb-3">
          <SOULQuestionnaire
            workspaceId={workspaceId}
            onDone={() => { setShowQuestionnaire(false); regenerate(); }}
            onCancel={() => setShowQuestionnaire(false)}
          />
        </div>
      )}

      {loading ? (
        <Skeleton className="h-64 w-full rounded-lg" />
      ) : (
        <Textarea
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value)
            setDirty(e.target.value !== (persona?.content_md ?? ''))
          }}
          placeholder="# Identity&#10;(Click Regenerate to synthesize from your preferences and résumé)"
          className="min-h-[240px] font-mono text-[12.5px] leading-relaxed"
        />
      )}

      <div className="mt-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground/70">
          <span className="font-mono">{charCount} chars</span>
          {persona && (
            <span className="font-mono">
              updated {formatRelativeTime(persona.updated_at)}
            </span>
          )}
          {error && <span className="text-destructive">{error}</span>}
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setShowQuestionnaire(v => !v)}
            disabled={busy !== null}
            className="gap-1.5"
          >
            <ClipboardList className="h-3.5 w-3.5" />
            Questionnaire
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => regenerate()}
            disabled={busy !== null}
          >
            {busy === 'regenerate' ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
            )}
            Regenerate
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={() => save(draft)}
            disabled={busy !== null || !dirty}
          >
            {busy === 'save' ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="mr-1.5 h-3.5 w-3.5" />
            )}
            Save
          </Button>
        </div>
      </div>
    </section>
  )
}
