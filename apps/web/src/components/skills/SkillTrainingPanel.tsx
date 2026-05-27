'use client'
import { useCallback, useState } from 'react'
import { Brain, CheckCircle2, ChevronDown, ChevronRight, Loader2, Play, XCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import { useSkillTrainingRuns, useStartTraining, useTrainingModeToggle, type TrainingRun } from '@/lib/useSkillTraining'

interface Props {
  skillId: string
  skillName: string
  agentId: string
  workspaceId: string
  trainingMode: string | null
}

function EpochTimeline({ run }: { run: TrainingRun }) {
  const epochs = run.epochs ?? []
  if (epochs.length === 0) return null
  return (
    <div className="mt-2 space-y-1 pl-2">
      {epochs.map((ep) => (
        <div key={ep.epoch} className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="w-14 shrink-0">Epoch {ep.epoch + 1}</span>
          <span className={cn('font-mono', ep.accepted ? 'text-green-600' : 'text-red-500')}>
            {ep.eval_score.toFixed(3)}
          </span>
          <span className="text-muted-foreground/50">vs {ep.baseline_score.toFixed(3)}</span>
          {ep.accepted ? (
            <CheckCircle2 className="h-3 w-3 text-green-600" />
          ) : (
            <XCircle className="h-3 w-3 text-red-500" />
          )}
          <span>{ep.patch_count} patch{ep.patch_count !== 1 ? 'es' : ''}</span>
        </div>
      ))}
    </div>
  )
}

function RunStatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800',
    running: 'bg-blue-100 text-blue-800',
    done: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  }
  return (
    <span className={cn('rounded px-1.5 py-0.5 text-xs font-medium', map[status] ?? 'bg-muted text-muted-foreground')}>
      {status}
    </span>
  )
}

function RunRow({ run }: { run: TrainingRun }) {
  const [open, setOpen] = useState(false)
  const date = new Date(run.created_at).toLocaleDateString()
  return (
    <div className="rounded border px-3 py-2">
      <button className="flex w-full items-center gap-2 text-left" onClick={() => setOpen(o => !o)}>
        {open ? <ChevronDown className="h-3 w-3 shrink-0" /> : <ChevronRight className="h-3 w-3 shrink-0" />}
        <RunStatusBadge status={run.status} />
        <span className="flex-1 text-xs text-muted-foreground">{date}</span>
        {run.best_score != null && (
          <span className="font-mono text-xs">best: {run.best_score.toFixed(3)}</span>
        )}
        {run.accepted && <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />}
      </button>
      {open && <EpochTimeline run={run} />}
    </div>
  )
}

export function SkillTrainingPanel({ skillId, skillName, agentId, workspaceId, trainingMode }: Props) {
  const { runs, loading, reload, startPolling } = useSkillTrainingRuns(skillId)

  const handleStarted = useCallback(() => {
    reload()
    startPolling()
  }, [reload, startPolling])

  const { start, busy: trainBusy, error: trainError } = useStartTraining(skillId, agentId, workspaceId, handleStarted)
  const { toggle: toggleMode, busy: modeBusy } = useTrainingModeToggle(skillId, reload)

  const isTrainingEnabled = trainingMode === 'react'
  const hasActiveRun = runs.some(r => r.status === 'pending' || r.status === 'running')

  return (
    <div className="rounded-lg border bg-card p-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium">{skillName}</span>
          {isTrainingEnabled && (
            <Badge variant="secondary" className="text-xs">auto-train</Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Toggle training mode */}
          <Button
            variant="outline"
            size="sm"
            disabled={modeBusy}
            onClick={() => void toggleMode(!isTrainingEnabled)}
            className="h-7 text-xs"
          >
            {modeBusy ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : isTrainingEnabled ? (
              'Disable auto-train'
            ) : (
              'Enable auto-train'
            )}
          </Button>
          {/* Train now */}
          <Button
            size="sm"
            disabled={trainBusy || hasActiveRun}
            onClick={() => void start()}
            className="h-7 gap-1 text-xs"
          >
            {trainBusy || hasActiveRun ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Play className="h-3 w-3" />
            )}
            {hasActiveRun ? 'Training…' : 'Train now'}
          </Button>
        </div>
      </div>

      {trainError && (
        <p className="mt-2 text-xs text-red-500">{trainError}</p>
      )}

      {/* Run history */}
      {!loading && runs.length > 0 && (
        <>
          <Separator className="my-3" />
          <p className="mb-2 text-xs font-medium text-muted-foreground">Training history</p>
          <div className="space-y-1.5">
            {runs.slice(0, 5).map(run => (
              <RunRow key={run.id} run={run} />
            ))}
          </div>
        </>
      )}

      {loading && (
        <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin" />
          Loading…
        </div>
      )}
    </div>
  )
}
