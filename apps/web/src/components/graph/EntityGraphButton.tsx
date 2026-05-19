'use client'
import { useState } from 'react'
import { EntityGraphPanel } from './EntityGraphPanel'
import type { NodeType } from '@/lib/graph/types'

interface EntityGraphButtonProps {
  workspaceId: string
  nodeType: NodeType
  refId: string
}

export function EntityGraphButton({
  workspaceId,
  nodeType,
  refId,
}: EntityGraphButtonProps) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button
        onClick={() => setOpen(o => !o)}
        title="Show entity graph"
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded
                   bg-slate-800 border border-slate-700 text-slate-400
                   hover:border-indigo-500 hover:text-indigo-400
                   text-xs transition-colors"
      >
        <svg
          width="12" height="12" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2"
        >
          <circle cx="12" cy="5" r="3" />
          <circle cx="5" cy="19" r="3" />
          <circle cx="19" cy="19" r="3" />
          <line x1="12" y1="8" x2="5" y2="16" />
          <line x1="12" y1="8" x2="19" y2="16" />
        </svg>
        Graph
      </button>

      {open && (
        <EntityGraphPanel
          workspaceId={workspaceId}
          nodeType={nodeType}
          refId={refId}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  )
}
