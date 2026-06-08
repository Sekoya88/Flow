'use client'
import { CheckCircle2, Download, GitBranch, Loader2, MinusCircle, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  useCollections,
  useImportCollection,
  type ImportStep,
} from '@/lib/useSkillCollections'

function StepRow({ s }: { s: ImportStep }) {
  const icon =
    s.status === 'installed' ? <CheckCircle2 className="h-3 w-3 text-emerald-400" /> :
    s.status === 'skipped'  ? <MinusCircle className="h-3 w-3 text-flow-500" /> :
                              <XCircle className="h-3 w-3 text-red-400" />
  return (
    <div className="flex items-center gap-2 font-mono text-[10px]">
      <span className="shrink-0">{icon}</span>
      <span className="text-flow-300 truncate">{s.name}</span>
      <span className="text-flow-600 truncate">— {s.reason}</span>
    </div>
  )
}

export function CuratedCollections({ workspaceId }: { workspaceId: string | undefined }) {
  const { collections, loading, error } = useCollections()
  const { importCollection, busyId, results, errors } = useImportCollection(workspaceId)

  if (loading) {
    return (
      <div className="flex items-center gap-2 font-mono text-[11px] text-flow-500">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading collections…
      </div>
    )
  }
  if (error) return <p className="font-mono text-[11px] text-red-400">{error}</p>

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-flow-100">Curated collections</h2>
        <p className="text-[12px] text-muted-foreground">
          One-click import of vetted skills from public repos. Every step is shown below.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {collections.map((c) => {
          const res = results[c.id]
          const err = errors[c.id]
          const busy = busyId === c.id
          return (
            <div key={c.id} className="rounded-xl border border-flow-800 bg-flow-900 p-4 space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-mono text-sm font-semibold text-flow-100 truncate">{c.name}</p>
                  <a
                    href={`https://github.com/${c.repo}`}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-0.5 inline-flex items-center gap-1 font-mono text-[10px] text-flow-500 hover:text-flow-300"
                  >
                    <GitBranch className="h-3 w-3" /> {c.repo}
                  </a>
                </div>
                <span className="shrink-0 rounded border border-flow-violet/30 bg-flow-violet/10 px-1.5 py-0.5 font-mono text-[10px] text-flow-violet">
                  {c.category}
                </span>
              </div>

              <p className="text-[12px] leading-relaxed text-muted-foreground line-clamp-2">{c.description}</p>

              <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] text-flow-600">{c.skill_count} skills</span>
                <button
                  disabled={busy || !workspaceId}
                  onClick={() => void importCollection(c.id)}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-md bg-flow-violet px-3 py-1.5 font-mono text-[11px] text-white transition-colors hover:bg-flow-violet/90 disabled:opacity-50',
                  )}
                >
                  {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
                  {busy ? 'Importing…' : res ? 'Re-import' : 'Import'}
                </button>
              </div>

              {err && <p className="font-mono text-[10px] text-red-400">{err}</p>}

              {res && (
                <div className="space-y-1.5 rounded-md border border-flow-800 bg-flow-950 p-2.5">
                  <p className="font-mono text-[10px] uppercase tracking-wider text-flow-500">
                    {res.installed} installed · {res.skipped} skipped · {res.errors} errors
                  </p>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {res.steps.map((s) => <StepRow key={s.path} s={s} />)}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
