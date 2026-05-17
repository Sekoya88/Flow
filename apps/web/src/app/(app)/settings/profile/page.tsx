'use client'

import { useRef } from 'react'
import { AlertTriangle, FileUp, Layers, Loader2, UserCog } from 'lucide-react'
import { usePreferences } from '@/lib/usePreferences'
import { useWorkspaceId } from '@/lib/useWorkspace'
import { PreferenceSection } from '@/components/preferences/PreferenceSection'
import { CandidateQueue } from '@/components/preferences/CandidateQueue'
import { CVDropzone } from '@/components/preferences/CVDropzone'
import { PersonaSection } from '@/components/preferences/PersonaSection'

const FACET_CLASSES = ['style', 'tooling', 'goal', 'veto', 'domain', 'channel'] as const

export default function ProfilePage() {
  const candidateSectionRef = useRef<HTMLDivElement>(null)
  const { workspaceId, loading: wsLoading } = useWorkspaceId()
  const { data, loading, error, reload, patchPreference, createPreference } =
    usePreferences(workspaceId ?? '')

  if (wsLoading || loading) {
    return (
      <div className="mx-auto flex max-w-2xl items-center justify-center gap-2 px-4 py-16 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>Loading preferences…</span>
      </div>
    )
  }
  if (!workspaceId) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-sm text-destructive">
        No workspace found. Sign in again.
      </div>
    )
  }
  if (error) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-sm text-destructive">
        Failed to load preferences.
      </div>
    )
  }

  const global = data?.global ?? []
  const candidates = global.filter(p => p.status === 'candidate')

  function scrollToCandidates() {
    candidateSectionRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  async function handleBulkPromote() {
    await Promise.all(candidates.map(p => patchPreference(p.id, 'promote')))
  }

  async function handleBulkDismiss() {
    await Promise.all(candidates.map(p => patchPreference(p.id, 'forget')))
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-8 px-4 pb-12 pt-6 animate-fade-in">
      {/* Header */}
      <header className="space-y-2">
        <div className="flex items-center gap-2">
          <UserCog className="h-4 w-4 text-flow-amber" />
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-flow-amber/80">
            Profile
          </span>
        </div>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          Your preferences
        </h1>
        <p className="text-sm text-muted-foreground">
          Tune how every agent run feels. Pinned facets stay forever; candidates graduate as they prove themselves.
        </p>
      </header>

      {/* Pending review banner */}
      {candidates.length > 0 && (
        <button
          onClick={scrollToCandidates}
          className="flow-card flex w-full items-center gap-3 rounded-[6px] border border-amber-500/30 px-4 py-3 text-left transition-colors hover:border-amber-500/60 hover:bg-amber-500/[0.04]"
        >
          <AlertTriangle className="h-4 w-4 text-amber-400" />
          <div className="flex-1">
            <p className="text-sm font-medium text-amber-200">
              {candidates.length} preference{candidates.length !== 1 ? 's' : ''} pending review
            </p>
            <p className="font-mono text-[11px] text-amber-200/60">
              Promote or dismiss them below
            </p>
          </div>
        </button>
      )}

      {/* SOUL.md persona */}
      <PersonaSection workspaceId={workspaceId} />

      {/* CV import */}
      <section className="flow-card rounded-[6px] border border-flow-800 p-5">
        <div className="mb-4 flex items-center gap-2">
          <FileUp className="h-3.5 w-3.5 text-flow-amber" />
          <h2 className="text-sm font-semibold text-foreground">
            Import from Résumé
          </h2>
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60">
            optional
          </span>
        </div>
        <CVDropzone workspaceId={workspaceId} onImported={() => reload()} />
      </section>

      {/* Facets */}
      <section className="flow-card rounded-[6px] border border-flow-800 p-2">
        <div className="mb-2 flex items-center gap-2 px-3 pt-2">
          <Layers className="h-3.5 w-3.5 text-flow-amber" />
          <h2 className="text-sm font-semibold text-foreground">Facets</h2>
        </div>
        <div className="space-y-1">
          {FACET_CLASSES.map(cls => (
            <PreferenceSection
              key={cls}
              cls={cls}
              prefs={global.filter(p => p.class === cls)}
              onPatch={patchPreference}
              onAdd={(c, val) => createPreference(c, val)}
            />
          ))}
        </div>
      </section>

      {/* Candidate queue */}
      <section ref={candidateSectionRef} id="candidate-section">
        <CandidateQueue
          candidates={candidates}
          onPatch={patchPreference}
          onBulkPromote={handleBulkPromote}
          onBulkDismiss={handleBulkDismiss}
        />
      </section>
    </div>
  )
}
