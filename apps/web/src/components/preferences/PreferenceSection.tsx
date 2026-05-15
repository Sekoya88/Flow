'use client'
import { useState } from 'react'
import type { Preference } from '@/lib/usePreferences'
import { PreferenceRow } from './PreferenceRow'
import { AddPreferenceInline } from './AddPreferenceInline'

interface PreferenceSectionProps {
  cls: string
  prefs: Preference[]
  onPatch: (id: string, action: string) => void
  onAdd: (cls: string, value: string) => void
  readOnly?: boolean
  globalPrefs?: Preference[]
}

export function PreferenceSection({
  cls,
  prefs,
  onPatch,
  onAdd,
  readOnly,
  globalPrefs,
}: PreferenceSectionProps) {
  const [open, setOpen] = useState(true)

  return (
    <div className="border border-slate-700 rounded-lg mb-3 overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-slate-800 hover:bg-slate-700/80"
      >
        <span className="text-sm font-semibold text-slate-200 capitalize">{cls}</span>
        <span className="text-slate-500 text-xs">{open ? '▲' : '▼'} {prefs.length}</span>
      </button>

      {open && (
        <div className="px-2 pb-2">
          {globalPrefs && globalPrefs.length > 0 && (
            <div className="mt-1 mb-1">
              {globalPrefs.map(p => (
                <PreferenceRow key={p.id} pref={p} onPatch={onPatch} readOnly label="Global" />
              ))}
            </div>
          )}
          {prefs.map(p => (
            <PreferenceRow key={p.id} pref={p} onPatch={onPatch} readOnly={readOnly} />
          ))}
          {!readOnly && (
            <AddPreferenceInline cls={cls} onAdd={onAdd} />
          )}
        </div>
      )}
    </div>
  )
}
