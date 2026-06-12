'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { CheckCircle2, Clock, Loader2, XCircle } from 'lucide-react'
import { FlowPageHeader } from '@/components/layout/FlowPageHeader'
import { apiFetch } from '@/lib/api'
import { cn } from '@/lib/utils'

type ExecutionRow = {
  id: string
  status: 'running' | 'completed' | 'failed'
  agent_id: string
  agent_name: string
  user_message: string
  answer: string
  thread_id: string
  created_at: string | null
  completed_at: string | null
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    running: 'bg-flow-violet/15 text-flow-violet border-flow-violet/30',
    completed: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    failed: 'bg-red-500/15 text-red-400 border-red-500/30',
  }
  return (
    <span className={cn(
      'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider',
      styles[status] ?? 'bg-flow-800 text-flow-400 border-flow-700'
    )}>
      {status === 'running' && <Loader2 className="h-2.5 w-2.5 animate-spin" />}
      {status === 'completed' && <CheckCircle2 className="h-2.5 w-2.5" />}
      {status === 'failed' && <XCircle className="h-2.5 w-2.5" />}
      {status}
    </span>
  )
}

function duration(created: string | null, completed: string | null): string | null {
  if (!created || !completed) return null
  const ms = new Date(completed).getTime() - new Date(created).getTime()
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

const PAGE_SIZE = 60

export default function ExecutionsPage() {
  const [executions, setExecutions] = useState<ExecutionRow[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)

  useEffect(() => {
    apiFetch<{ executions: ExecutionRow[]; has_more: boolean }>(`/api/v1/executions?limit=${PAGE_SIZE}&offset=0`)
      .then((res) => {
        setExecutions(res.executions ?? [])
        setHasMore(res.has_more ?? false)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const loadMore = () => {
    setLoadingMore(true)
    apiFetch<{ executions: ExecutionRow[]; has_more: boolean }>(
      `/api/v1/executions?limit=${PAGE_SIZE}&offset=${executions.length}`,
    )
      .then((res) => {
        setExecutions((prev) => [...prev, ...(res.executions ?? [])])
        setHasMore(res.has_more ?? false)
      })
      .catch(() => {})
      .finally(() => setLoadingMore(false))
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <FlowPageHeader
        title="Executions"
        description="Full run history across all agents."
      />

      {loading && (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm">Loading…</span>
        </div>
      )}

      {!loading && executions.length === 0 && (
        <p className="text-sm text-muted-foreground">No executions yet. Run an agent to get started.</p>
      )}

      {executions.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-flow-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-flow-800 bg-flow-950">
                <th className="px-4 py-2.5 text-left font-mono text-[10px] uppercase tracking-wider text-flow-500">Status</th>
                <th className="px-4 py-2.5 text-left font-mono text-[10px] uppercase tracking-wider text-flow-500">Agent</th>
                <th className="px-4 py-2.5 text-left font-mono text-[10px] uppercase tracking-wider text-flow-500">Message</th>
                <th className="px-4 py-2.5 text-right font-mono text-[10px] uppercase tracking-wider text-flow-500">Duration</th>
                <th className="px-4 py-2.5 text-right font-mono text-[10px] uppercase tracking-wider text-flow-500">Date</th>
              </tr>
            </thead>
            <tbody>
              {executions.map((ex, i) => {
                const dur = duration(ex.created_at, ex.completed_at)
                const date = ex.created_at
                  ? new Date(ex.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
                  : '—'
                return (
                  <tr
                    key={ex.id}
                    className={cn(
                      'border-b border-flow-800/60 transition-colors hover:bg-flow-900/60',
                      i === executions.length - 1 && 'border-b-0'
                    )}
                  >
                    <td className="px-4 py-3">
                      <StatusBadge status={ex.status} />
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-flow-300">{ex.agent_name}</td>
                    <td className="px-4 py-3 max-w-xs">
                      <Link
                        href={`/executions/${ex.id}`}
                        className="block truncate font-mono text-xs text-flow-400 hover:text-flow-100 transition-colors"
                        title={ex.user_message}
                      >
                        {ex.user_message || '(no message)'}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {dur ? (
                        <span className="inline-flex items-center gap-1 font-mono text-[10px] text-flow-500">
                          <Clock className="h-2.5 w-2.5" />
                          {dur}
                        </span>
                      ) : (
                        <span className="font-mono text-[10px] text-flow-700">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-[10px] text-flow-500 whitespace-nowrap">{date}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {hasMore && (
        <button
          type="button"
          onClick={loadMore}
          disabled={loadingMore}
          className="mx-auto inline-flex items-center gap-2 rounded-md border border-flow-800 bg-flow-900 px-4 py-2 font-mono text-xs text-flow-300 transition-colors hover:bg-flow-800 hover:text-flow-100 disabled:opacity-50"
        >
          {loadingMore && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {loadingMore ? 'Loading…' : 'Load more'}
        </button>
      )}
    </div>
  )
}
