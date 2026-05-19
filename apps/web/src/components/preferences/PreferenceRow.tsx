'use client'
import type { Preference } from '@/lib/usePreferences'

const STATUS_BADGE: Record<string, string> = {
  candidate: 'bg-slate-700 text-slate-300',
  provisional: 'bg-amber-900/60 text-amber-300',
  active: 'bg-emerald-900/60 text-emerald-300',
}

interface PreferenceRowProps {
  pref: Preference
  onPatch: (id: string, action: string) => void
  readOnly?: boolean
  label?: string
}

export function PreferenceRow({ pref, onPatch, readOnly, label }: PreferenceRowProps) {
  const badgeCls = pref.pinned
    ? 'bg-indigo-900/60 text-indigo-300'
    : STATUS_BADGE[pref.status] ?? STATUS_BADGE.candidate

  const badgeText = pref.pinned ? 'pinned' : pref.status === 'provisional' ? 'learning' : pref.status

  return (
    <div className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-slate-800/50 group">
      <span className="flex-1 text-sm text-slate-200">{pref.value}</span>
      {label && (
        <span className="text-xs text-slate-500 italic">{label}</span>
      )}
      <span className={`text-xs px-1.5 py-0.5 rounded ${badgeCls}`}>{badgeText}</span>
      <div className="w-12 h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-indigo-500 rounded-full"
          style={{ width: `${Math.round(pref.score * 100)}%` }}
        />
      </div>
      {!readOnly && (
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {pref.status !== 'active' && !pref.pinned && (
            <button
              title="Promote"
              onClick={() => onPatch(pref.id, 'promote')}
              className="text-slate-400 hover:text-emerald-400 text-xs"
            >
              ↑
            </button>
          )}
          {!pref.pinned ? (
            <button
              title="Pin"
              onClick={() => onPatch(pref.id, 'pin')}
              className="text-slate-400 hover:text-indigo-400 text-xs"
            >
              ⚑
            </button>
          ) : (
            <button
              title="Unpin"
              onClick={() => onPatch(pref.id, 'unpin')}
              className="text-indigo-400 hover:text-slate-400 text-xs"
            >
              ⚑
            </button>
          )}
          <button
            title="Veto"
            onClick={() => onPatch(pref.id, 'veto')}
            className="text-slate-400 hover:text-red-400 text-xs"
          >
            🚫
          </button>
          <button
            title="Forget"
            onClick={() => onPatch(pref.id, 'forget')}
            className="text-slate-400 hover:text-red-400 text-xs"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  )
}
