'use client'
import { useState } from 'react'

interface AddPreferenceInlineProps {
  cls: string
  onAdd: (cls: string, value: string) => void
}

export function AddPreferenceInline({ cls, onAdd }: AddPreferenceInlineProps) {
  const [value, setValue] = useState('')
  const [adding, setAdding] = useState(false)

  const submit = () => {
    const v = value.trim()
    if (!v) return
    onAdd(cls, v)
    setValue('')
    setAdding(false)
  }

  if (!adding) {
    return (
      <button
        onClick={() => setAdding(true)}
        className="text-xs text-slate-500 hover:text-slate-300 mt-1 ml-2"
      >
        + Add {cls} preference
      </button>
    )
  }

  return (
    <div className="flex gap-2 mt-2 ml-2">
      <input
        autoFocus
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') submit(); if (e.key === 'Escape') setAdding(false) }}
        placeholder={`e.g. uses TypeScript`}
        className="flex-1 text-sm bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
      />
      <button onClick={submit} className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-2 py-1 rounded">
        Add
      </button>
      <button onClick={() => setAdding(false)} className="text-xs text-slate-500 hover:text-slate-300">
        Cancel
      </button>
    </div>
  )
}
