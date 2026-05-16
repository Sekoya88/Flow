'use client'
import { useEffect, useState } from 'react'
import { AlertTriangle, Loader2, RefreshCw, Save, Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { usePersona } from '@/lib/usePersona'

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

export function PersonaSection({ workspaceId }: PersonaSectionProps) {
  const { persona, loading, busy, error, save, regenerate } = usePersona(workspaceId)
  const [draft, setDraft] = useState('')
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    setDraft(persona?.content_md ?? '')
    setDirty(false)
  }, [persona?.content_md, persona?.version])

  const chips = persona ? derivationChips(persona.derived_from ?? {}) : []
  const charCount = draft.length
  const isStale = Boolean(persona?.derived_from?.stale_since)

  return (
    <section className="surface-glass rounded-2xl border border-border/50 p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-3.5 w-3.5 text-flow-brand" />
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
                  ? 'border-flow-brand/40 bg-flow-brand/10 text-flow-brand'
                  : 'border-border/40 text-muted-foreground'
              }
            >
              {c.label}
            </Badge>
          ))}
        </div>
      </div>

      <p className="mb-3 text-xs text-muted-foreground">
        Identity block injected as the first system message of every agent run.
        Regenerate from your facets + CV, or edit by hand.
      </p>

      {isStale && (
        <div className="mb-3 flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-600 dark:text-amber-400">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          Your preferences have changed since this was last regenerated — click Regenerate to refresh.
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
