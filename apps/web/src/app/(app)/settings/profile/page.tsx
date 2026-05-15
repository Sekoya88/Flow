'use client'

import { useRef } from 'react'
import { usePreferences } from '@/lib/usePreferences'
import { PreferenceSection } from '@/components/preferences/PreferenceSection'
import { CandidateQueue } from '@/components/preferences/CandidateQueue'
import { CVDropzone } from '@/components/preferences/CVDropzone'

const WORKSPACE_ID = 'default'
const FACET_CLASSES = ['style', 'tooling', 'goal', 'veto', 'domain', 'channel'] as const

export default function ProfilePage() {
  const candidateSectionRef = useRef<HTMLDivElement>(null)
  const { data, loading, error, reload, patchPreference, createPreference } =
    usePreferences(WORKSPACE_ID)

  if (loading) return <p className="p-6 text-slate-400">Loading preferences...</p>
  if (error) return <p className="p-6 text-red-400">Failed to load preferences.</p>

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
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-8">
      <h1 className="text-2xl font-bold text-slate-100">Profile</h1>

      {candidates.length > 0 && (
        <button
          onClick={scrollToCandidates}
          className="w-full text-left px-4 py-3 rounded-lg bg-amber-900/40 border border-amber-700/60 text-amber-300 text-sm hover:bg-amber-900/60"
        >
          {candidates.length} preference{candidates.length !== 1 ? 's' : ''} pending review
        </button>
      )}

      <section>
        <h2 className="text-base font-semibold text-slate-200 mb-3">Import from Résumé</h2>
        <CVDropzone workspaceId={WORKSPACE_ID} onImported={() => reload()} />
      </section>

      <section className="space-y-1">
        {FACET_CLASSES.map(cls => (
          <PreferenceSection
            key={cls}
            cls={cls}
            prefs={global.filter(p => p.class === cls && p.status !== 'candidate')}
            onPatch={patchPreference}
            onAdd={(c, val) => createPreference(c, val)}
          />
        ))}
      </section>

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
