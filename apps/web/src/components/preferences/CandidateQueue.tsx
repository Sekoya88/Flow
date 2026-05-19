'use client'
import type { Preference } from '@/lib/usePreferences'
import { PreferenceRow } from '@/components/preferences/PreferenceRow'

interface CandidateQueueProps {
  candidates: Preference[]
  onPatch: (id: string, action: string) => void
  onBulkPromote: () => void
  onBulkDismiss: () => void
}

export function CandidateQueue({ candidates, onPatch, onBulkPromote, onBulkDismiss }: CandidateQueueProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-slate-200">Pending Review</h3>
          <span className="text-xs px-1.5 py-0.5 rounded bg-slate-700 text-slate-300">
            {candidates.length}
          </span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onBulkPromote}
            disabled={candidates.length === 0}
            className="text-xs px-2 py-1 rounded bg-emerald-900/60 text-emerald-300 hover:bg-emerald-800/60 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Promote all
          </button>
          <button
            onClick={onBulkDismiss}
            disabled={candidates.length === 0}
            className="text-xs px-2 py-1 rounded bg-slate-700 text-slate-300 hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Dismiss all
          </button>
        </div>
      </div>
      {candidates.length === 0 ? (
        <p className="text-sm text-slate-500 py-2">No candidates pending review</p>
      ) : (
        <div>
          {candidates.map((pref) => (
            <PreferenceRow key={pref.id} pref={pref} onPatch={onPatch} />
          ))}
        </div>
      )}
    </div>
  )
}
