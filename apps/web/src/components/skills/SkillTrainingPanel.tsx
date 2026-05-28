'use client'
import { useCallback, useEffect, useState } from 'react'
import {
  AlertCircle,
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Layers,
  Loader2,
  Play,
  TrendingUp,
  XCircle,
  Zap,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useStore } from '@/lib/store'
import { useSkillTrainingRuns, useStartTraining, useTrainingModeToggle, type TrainingRun } from '@/lib/useSkillTraining'

interface Props {
  skillId: string
  skillName: string
  agentId: string
  workspaceId: string
  trainingMode: string | null
}

const STAGE_LABELS = ['Rollout', 'Reflect', 'Aggregate', 'Select', 'Update', 'Evaluate']
const MAX_EPOCHS = 3

function StatusDot({ status }: { status: string }) {
  const base = "h-2 w-2 rounded-full shrink-0"
  if (status === 'running') return <span className={cn(base, "bg-flow-violet animate-pulse")} />
  if (status === 'done') return <span className={cn(base, "bg-emerald-500")} />
  if (status === 'failed') return <span className={cn(base, "bg-red-500")} />
  return <span className={cn(base, "bg-flow-700")} />
}

function RunStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    running: 'bg-flow-violet/15 text-flow-violet border-flow-violet/30',
    done: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    failed: 'bg-red-500/15 text-red-400 border-red-500/30',
  }
  return (
    <span className={cn(
      'inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider',
      styles[status] ?? 'bg-flow-800 text-flow-400 border-flow-700'
    )}>
      {status === 'running' && <Loader2 className="mr-1 h-2.5 w-2.5 animate-spin" />}
      {status}
    </span>
  )
}

function EpochTimeline({ run }: { run: TrainingRun }) {
  const epochs = run.epochs ?? []
  if (epochs.length === 0) return null
  return (
    <div className="mt-3 space-y-2 rounded-md bg-flow-950 p-3">
      <p className="mb-2 font-mono text-[10px] uppercase tracking-wider text-flow-500">Epoch results</p>
      {epochs.map((ep) => (
        <div key={ep.epoch} className="flex items-center gap-3">
          <span className="w-14 font-mono text-[10px] text-flow-500">Epoch {ep.epoch + 1}</span>
          <div className="flex flex-1 items-center gap-2">
            <div className="flex-1 rounded bg-flow-800 h-1.5 overflow-hidden">
              <div
                className={cn("h-full rounded transition-all", ep.accepted ? "bg-emerald-500" : "bg-red-500")}
                style={{ width: `${Math.min(ep.eval_score * 100, 100)}%` }}
              />
            </div>
            <div className="flex items-center gap-1.5">
              <span className={cn("font-mono text-xs font-semibold", ep.accepted ? "text-emerald-400" : "text-red-400")}>
                {ep.eval_score.toFixed(3)}
              </span>
              <span className={cn("font-mono text-[10px]", ep.accepted ? "text-emerald-500/70" : "text-red-500/70")}>
                {ep.accepted ? `+${(ep.eval_score - ep.baseline_score).toFixed(3)}` : (ep.eval_score - ep.baseline_score).toFixed(3)}
              </span>
            </div>
          </div>
          {ep.accepted ? (
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
          ) : (
            <XCircle className="h-3.5 w-3.5 shrink-0 text-red-500" />
          )}
          <span className="w-16 text-right font-mono text-[10px] text-flow-600">
            {ep.patch_count} patch{ep.patch_count !== 1 ? 'es' : ''}
          </span>
        </div>
      ))}
    </div>
  )
}

function ActiveRunProgress({ run }: { run: TrainingRun }) {
  const currentEpoch = run.epoch ?? 0
  const epochProgress = Math.min(currentEpoch / MAX_EPOCHS, 1)

  return (
    <div className="mt-3 space-y-3 rounded-md border border-flow-violet/20 bg-flow-violet/5 p-3">
      {/* Epoch counter */}
      <div className="flex items-center justify-between">
        <p className="font-mono text-[10px] uppercase tracking-wider text-flow-violet/70">Progress</p>
        <span className="font-mono text-[11px] text-flow-300">
          Epoch <span className="font-semibold text-flow-violet">{currentEpoch}</span> / {MAX_EPOCHS}
        </span>
      </div>

      {/* Epoch progress bar */}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-flow-800">
        <div
          className="h-full rounded-full bg-flow-violet transition-all duration-700"
          style={{ width: `${epochProgress * 100}%` }}
        />
      </div>

      {/* Pipeline stages */}
      <div className="flex items-center gap-0.5">
        {STAGE_LABELS.map((label, i) => {
          const isDone = i < currentEpoch % STAGE_LABELS.length && currentEpoch > 0
          const isActive = i === currentEpoch % STAGE_LABELS.length
          return (
            <div key={label} className="flex flex-1 flex-col items-center gap-1">
              <div className={cn(
                "flex h-5 w-5 items-center justify-center rounded-full border text-[8px] font-bold transition-colors",
                isActive
                  ? "border-flow-violet bg-flow-violet/20 text-flow-violet animate-pulse"
                  : isDone
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-500"
                  : "border-flow-700 bg-flow-900 text-flow-600"
              )}>
                {isDone ? '✓' : i + 1}
              </div>
              <span className="text-center font-mono text-[8px] leading-tight text-flow-600 truncate max-w-full px-0.5">{label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function RunCard({ run, defaultOpen }: { run: TrainingRun; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen ?? false)
  const date = new Date(run.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  const isActive = run.status === 'running' || run.status === 'pending'

  return (
    <div className={cn(
      "rounded-lg border transition-colors",
      isActive
        ? "border-flow-violet/30 bg-flow-violet/5"
        : "border-flow-800 bg-flow-900/50"
    )}>
      <button
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left min-w-0"
        onClick={() => setOpen(o => !o)}
      >
        <StatusDot status={run.status} />
        <RunStatusBadge status={run.status} />
        <span className="flex-1 truncate font-mono text-[11px] text-flow-400">{date}</span>
        {run.best_score != null && (
          <div className="flex shrink-0 items-center gap-1">
            <TrendingUp className="h-3 w-3 text-flow-500" />
            <span className="font-mono text-xs font-semibold text-flow-200">{run.best_score.toFixed(3)}</span>
          </div>
        )}
        {run.accepted && (
          <span className="shrink-0 rounded bg-emerald-500/15 px-1.5 py-0.5 font-mono text-[10px] text-emerald-400 border border-emerald-500/30">
            applied
          </span>
        )}
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-flow-500" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-flow-500" />
        )}
      </button>

      {/* Inline error preview — always visible for failed runs */}
      {run.status === 'failed' && run.error_message && !open && (
        <div className="flex items-start gap-2 border-t border-red-500/10 bg-red-500/5 px-3 py-2">
          <AlertCircle className="mt-0.5 h-3 w-3 shrink-0 text-red-400" />
          <p className="font-mono text-[10px] leading-relaxed text-red-400 line-clamp-2">{run.error_message}</p>
        </div>
      )}

      {open && (
        <div className="border-t border-flow-800 px-3 pb-3">
          {isActive && <ActiveRunProgress run={run} />}
          <EpochTimeline run={run} />
          {run.status === 'failed' && run.error_message && (
            <div className="mt-2 rounded-md border border-red-500/20 bg-red-500/5 p-2.5">
              <p className="mb-1 font-mono text-[10px] uppercase tracking-wider text-red-400/70">Error</p>
              <p className="font-mono text-[11px] leading-relaxed text-red-400 break-all">
                {run.error_message}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function SkillTrainingPanel({ skillId, skillName, agentId, workspaceId, trainingMode }: Props) {
  const { runs, loading, reload, startPolling } = useSkillTrainingRuns(skillId)
  const setActiveTask = useStore((s) => s.setActiveTask)

  const hasActiveRun = runs.some(r => r.status === 'pending' || r.status === 'running')
  const lastBestScore = runs.find(r => r.best_score != null)?.best_score ?? null
  const isTrainingEnabled = trainingMode === 'react'

  // Keep floating indicator alive while training, clear when done
  useEffect(() => {
    if (hasActiveRun) {
      setActiveTask({ type: 'training', label: `Training ${skillName}…`, href: '/skills' })
    } else {
      setActiveTask(null)
    }
  }, [hasActiveRun, skillName, setActiveTask])

  const handleStarted = useCallback(() => {
    reload()
    startPolling()
  }, [reload, startPolling])

  const { start, busy: trainBusy, error: trainError } = useStartTraining(skillId, agentId, workspaceId, handleStarted)
  const { toggle: toggleMode, busy: modeBusy } = useTrainingModeToggle(skillId, reload)

  async function handleTrainNow() {
    await start()
  }

  return (
    <div className="space-y-4">
      {/* Header card */}
      <div className="rounded-xl border border-flow-800 bg-flow-900 p-4">
        <div className="flex flex-col gap-3">
          {/* Skill name row */}
          <div className="flex items-center gap-2 min-w-0">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-flow-violet/15 border border-flow-violet/30">
              <Brain className="h-3.5 w-3.5 text-flow-violet" />
            </div>
            <span className="truncate font-mono text-sm font-semibold text-flow-100">{skillName}</span>
            {isTrainingEnabled && (
              <span className="shrink-0 rounded border border-flow-violet/30 bg-flow-violet/10 px-1.5 py-0.5 font-mono text-[10px] text-flow-violet">
                auto
              </span>
            )}
          </div>

          {/* Stats row */}
          {lastBestScore != null && (
            <div className="flex items-center gap-1.5 pl-9">
              <Zap className="h-3 w-3 text-flow-500" />
              <span className="font-mono text-[11px] text-flow-400">
                Best score: <span className="text-flow-200 font-semibold">{lastBestScore.toFixed(3)}</span>
              </span>
            </div>
          )}

          {/* Buttons row — own line, never overflows */}
          <div className="flex items-center gap-2 pl-9">
            <Button
              variant="ghost"
              size="sm"
              disabled={modeBusy}
              onClick={() => void toggleMode(!isTrainingEnabled)}
              className="h-7 border border-flow-700 bg-flow-800 text-[11px] text-flow-400 hover:bg-flow-700 hover:text-flow-200"
            >
              {modeBusy ? <Loader2 className="h-3 w-3 animate-spin" /> : isTrainingEnabled ? 'Disable auto' : 'Enable auto'}
            </Button>
            <Button
              size="sm"
              disabled={trainBusy || hasActiveRun}
              onClick={() => void handleTrainNow()}
              className="h-7 gap-1.5 bg-flow-violet text-xs font-medium text-white hover:bg-flow-violet/90 disabled:opacity-60"
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
          <div className="mt-3 rounded-md border border-red-500/20 bg-red-500/5 px-3 py-2">
            <p className="font-mono text-[11px] text-red-400">{trainError}</p>
          </div>
        )}
      </div>

      {/* Run history */}
      {loading && (
        <div className="flex items-center gap-2 px-1 py-2 text-xs text-flow-500">
          <Loader2 className="h-3 w-3 animate-spin" />
          Loading training history…
        </div>
      )}

      {!loading && runs.length === 0 && (
        <div className="rounded-xl border border-dashed border-flow-800 bg-flow-950/50 px-5 py-6 text-center">
          <Layers className="mx-auto mb-2 h-7 w-7 text-flow-700" />
          <p className="font-mono text-xs font-medium text-flow-400">No training runs yet</p>
          <p className="mt-1 text-[11px] leading-relaxed text-flow-600">
            Mark agent responses as "Golden" in the Run page,<br />then click "Train now" to start.
          </p>
        </div>
      )}

      {!loading && runs.length > 0 && (
        <div className="space-y-2">
          <p className="px-0.5 font-mono text-[10px] uppercase tracking-wider text-flow-500">
            Training history · {runs.length} run{runs.length !== 1 ? 's' : ''}
          </p>
          {runs.slice(0, 6).map((run, i) => (
            <RunCard key={run.id} run={run} defaultOpen={i === 0 && (run.status === 'running' || run.status === 'pending' || run.status === 'failed')} />
          ))}
        </div>
      )}
    </div>
  )
}
