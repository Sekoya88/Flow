'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertCircle,
  BookOpen,
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Eye,
  GitBranch,
  Layers,
  Loader2,
  Minus,
  Play,
  Plus,
  TrendingUp,
  XCircle,
  Zap,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useStore } from '@/lib/store'
import {
  useGoldenSets,
  useGoldenSetItems,
  useOverrideTraining,
  useSkillTrainingRuns,
  useStartTraining,
  useTrainingEvents,
  useTrainingModeToggle,
  type ItemScore,
  type TrainingEvent,
  type TrainingPatch,
  type TrainingRun,
} from '@/lib/useSkillTraining'

interface Props {
  skillId: string
  skillName: string
  agentId: string
  workspaceId: string
  trainingMode: string | null
  initialOpen?: boolean
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

// Regression floor mirrored from the backend gate (TrainingConfig.regression_floor).
const REGRESSION_FLOOR = 0.1

// Flatten the latest epoch's per-item scores (that's the candidate the gate judged).
function latestItemScores(run: TrainingRun): ItemScore[] {
  const epochs = run.epochs ?? []
  for (let i = epochs.length - 1; i >= 0; i--) {
    if (epochs[i].item_scores && epochs[i].item_scores!.length) return epochs[i].item_scores!
  }
  return []
}

type Verdict = { kind: 'accepted' | 'blocked' | 'rejected'; worst?: ItemScore }

function runVerdict(run: TrainingRun): Verdict | null {
  if (run.status !== 'done') return null
  const items = latestItemScores(run)
  const worst = items.reduce<ItemScore | undefined>((acc, i) => (!acc || i.delta < acc.delta ? i : acc), undefined)
  if (run.accepted) return { kind: 'accepted', worst }
  if (worst && worst.delta < -REGRESSION_FLOOR) return { kind: 'blocked', worst }
  return { kind: 'rejected', worst }
}

function GateVerdict({ run, skillId, onOverride }: { run: TrainingRun; skillId: string; onOverride?: () => void }) {
  const v = runVerdict(run)
  const { override, busy, done } = useOverrideTraining(skillId, run.id, onOverride ?? (() => {}))
  if (!v) return null
  if (v.kind === 'blocked') {
    if (done) {
      return (
        <div className="mt-3 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
            <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
              ✓ Override approved — skill activated
            </span>
          </div>
        </div>
      )
    }
    return (
      <div className="mt-3 rounded-lg border-2 border-red-500 bg-red-500/15 px-3 py-2.5">
        <div className="flex items-center gap-2">
          <XCircle className="h-4 w-4 shrink-0 text-red-400" />
          <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-red-300">
            ⛔ Activation blocked — regression
          </span>
        </div>
        {v.worst && (
          <p className="mt-1 pl-6 font-mono text-[10px] leading-relaxed text-red-300/90">
            "{v.worst.input}" dropped {(v.worst.baseline_score * 100).toFixed(0)}% →{' '}
            {(v.worst.candidate_score * 100).toFixed(0)}% ({(v.worst.delta * 100).toFixed(0)}%). Filed a proposal for review.
          </p>
        )}
        <div className="mt-2 pl-6">
          <button
            onClick={override}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded border border-red-500/50 bg-red-500/20 px-2.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-red-200 transition-colors hover:bg-red-500/30 disabled:opacity-50"
          >
            {busy && <Loader2 className="h-3 w-3 animate-spin" />}
            Approve override
          </button>
        </div>
      </div>
    )
  }
  if (v.kind === 'accepted') {
    return (
      <div className="mt-3 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
          <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
            ✓ Accepted — no item regressed
          </span>
        </div>
      </div>
    )
  }
  return (
    <div className="mt-3 rounded-lg border border-flow-700 bg-flow-900 px-3 py-2">
      <span className="font-mono text-[10px] uppercase tracking-wider text-flow-400">
        ✗ Rejected — gain below threshold
      </span>
    </div>
  )
}

function ItemScores({ items }: { items: ItemScore[] }) {
  if (items.length === 0) return null
  return (
    <div className="mt-3 space-y-1.5 rounded-md bg-flow-950 p-3">
      <p className="mb-1 font-mono text-[10px] uppercase tracking-wider text-flow-500">
        Per-item before → after
      </p>
      {items.map((it) => {
        const regressed = it.delta < -REGRESSION_FLOOR
        return (
          <div key={it.item_id} className="flex items-center gap-2">
            <span className="flex-1 truncate font-mono text-[10px] text-flow-400" title={it.input}>
              {it.input}
            </span>
            <span className="shrink-0 font-mono text-[10px] text-flow-500">
              {(it.baseline_score * 100).toFixed(0)}→{(it.candidate_score * 100).toFixed(0)}
            </span>
            <span className={cn(
              'w-12 shrink-0 text-right font-mono text-[10px] font-semibold',
              regressed ? 'text-red-400' : it.delta > 0 ? 'text-emerald-400' : 'text-flow-500',
            )}>
              {it.delta >= 0 ? '+' : ''}{(it.delta * 100).toFixed(0)}%
            </span>
          </div>
        )
      })}
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

// ── Simple line-level diff (no library needed) ────────────────────────────────

function computeDiff(original: string, candidate: string): Array<{ type: 'same' | 'add' | 'remove'; line: string }> {
  const aLines = original.split('\n')
  const bLines = candidate.split('\n')
  // Build LCS matrix
  const m = aLines.length, n = bLines.length
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = 1; i <= m; i++)
    for (let j = 1; j <= n; j++)
      dp[i][j] = aLines[i - 1] === bLines[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1])
  // Trace back
  const result: Array<{ type: 'same' | 'add' | 'remove'; line: string }> = []
  let i = m, j = n
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && aLines[i - 1] === bLines[j - 1]) {
      result.unshift({ type: 'same', line: aLines[i - 1] })
      i--; j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ type: 'add', line: bLines[j - 1] })
      j--
    } else {
      result.unshift({ type: 'remove', line: aLines[i - 1] })
      i--
    }
  }
  return result
}

function SkillDiff({ original, candidate }: { original: string; candidate: string }) {
  const [show, setShow] = useState(false)
  const diff = computeDiff(original, candidate)
  const changes = diff.filter(d => d.type !== 'same').length
  if (changes === 0) return (
    <div className="mt-3 rounded-md border border-flow-800 bg-flow-950 px-3 py-2">
      <p className="font-mono text-[10px] text-flow-500">No changes to skill content.</p>
    </div>
  )
  return (
    <div className="mt-3 rounded-md border border-flow-800 bg-flow-950 overflow-hidden">
      <button
        className="flex w-full items-center justify-between px-3 py-2 text-left"
        onClick={() => setShow(s => !s)}
      >
        <div className="flex items-center gap-2">
          <GitBranch className="h-3 w-3 text-flow-500" />
          <span className="font-mono text-[10px] text-flow-400">Skill diff</span>
          <span className="font-mono text-[10px] text-emerald-400">+{diff.filter(d => d.type === 'add').length}</span>
          <span className="font-mono text-[10px] text-red-400">-{diff.filter(d => d.type === 'remove').length}</span>
        </div>
        {show ? <ChevronDown className="h-3 w-3 text-flow-500" /> : <ChevronRight className="h-3 w-3 text-flow-500" />}
      </button>
      {show && (
        <div className="border-t border-flow-800 overflow-x-auto">
          <pre className="p-3 font-mono text-[10px] leading-relaxed">
            {diff.map((d, i) => (
              <div
                key={i}
                className={cn(
                  "px-1",
                  d.type === 'add' ? 'bg-emerald-500/10 text-emerald-400' :
                  d.type === 'remove' ? 'bg-red-500/10 text-red-400' :
                  'text-flow-600'
                )}
              >
                <span className="select-none mr-2 opacity-50">
                  {d.type === 'add' ? <Plus className="inline h-2.5 w-2.5" /> : d.type === 'remove' ? <Minus className="inline h-2.5 w-2.5" /> : ' '}
                </span>
                {d.line || ' '}
              </div>
            ))}
          </pre>
        </div>
      )}
    </div>
  )
}

function PatchItem({ p }: { p: TrainingPatch }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className={cn(
      "rounded border px-2 py-1.5 text-[10px]",
      p.applied ? "border-emerald-500/20 bg-emerald-500/5" :
      p.rejected ? "border-red-500/20 bg-red-500/5" :
      "border-flow-800 bg-flow-900"
    )}>
      <button
        className="flex w-full items-center gap-1.5 text-left"
        onClick={() => p.content && setExpanded(x => !x)}
      >
        <span className={cn(
          "rounded px-1 py-px font-mono text-[9px] font-bold uppercase shrink-0",
          p.op === 'replace' ? "bg-amber-500/20 text-amber-400" :
          p.op === 'append' ? "bg-blue-500/20 text-blue-400" :
          p.op === 'insert' ? "bg-emerald-500/20 text-emerald-400" :
          "bg-red-500/20 text-red-400"
        )}>{p.op}</span>
        <span className="font-mono text-flow-400 truncate flex-1">{p.target}</span>
        {p.impact_score != null && (
          <span className="shrink-0 font-mono text-[9px] text-flow-600">{p.impact_score.toFixed(2)}</span>
        )}
        {p.content && (
          <span className="shrink-0 text-flow-700 ml-1">{expanded ? '▲' : '▼'}</span>
        )}
      </button>
      {expanded && p.content && (
        <pre className="mt-1.5 overflow-x-auto rounded border border-flow-800 bg-flow-950 p-2 font-mono text-[10px] leading-relaxed text-flow-300 whitespace-pre-wrap break-words">
          {p.content}
        </pre>
      )}
    </div>
  )
}

function PatchList({ patches }: { patches: TrainingPatch[] }) {
  if (patches.length === 0) return null
  const applied = patches.filter(p => p.applied)
  const rejected = patches.filter(p => p.rejected)
  return (
    <div className="mt-3 space-y-1.5 rounded-md border border-flow-800 bg-flow-950 p-3">
      <p className="mb-2 font-mono text-[10px] uppercase tracking-wider text-flow-500">
        Patches · {applied.length} applied · {rejected.length} rejected
      </p>
      {patches.map((p, i) => <PatchItem key={i} p={p} />)}
    </div>
  )
}

const STAGE_COLORS: Record<string, string> = {
  epoch: 'text-flow-violet',
  rollout: 'text-blue-400',
  reflect: 'text-amber-400',
  select: 'text-emerald-400',
  update: 'text-cyan-400',
  evaluate: 'text-purple-400',
}

const KIND_PREFIX: Record<string, string> = {
  stage_start: '▶',
  item_result: '·',
  analysis: '→',
  patch_proposed: '+',
  summary: '─',
  score: '★',
  error: '✗',
}

function EventRow({ event: e }: { event: TrainingEvent }) {
  const [expanded, setExpanded] = useState(false)
  const hasDetail = !!(e.data && (e.data.actual || e.data.rationale || e.data.analysis || e.data.content))

  return (
    <div className="space-y-0.5">
      <button
        className={cn(
          "flex w-full items-start gap-2 font-mono text-[10px] leading-relaxed text-left",
          hasDetail && "cursor-pointer hover:opacity-80",
        )}
        onClick={() => hasDetail && setExpanded(x => !x)}
      >
        <span className={cn('w-[52px] shrink-0 truncate font-semibold', STAGE_COLORS[e.stage] ?? 'text-flow-500')}>
          {e.stage}
        </span>
        <span className="shrink-0 w-3 text-flow-700 text-center">{KIND_PREFIX[e.kind] ?? '·'}</span>
        <span className="text-flow-400 break-words min-w-0 flex-1">{e.message}</span>
        {hasDetail && (
          <span className="shrink-0 text-flow-700">{expanded ? '▲' : '▼'}</span>
        )}
      </button>
      {expanded && e.data && (
        <div className="ml-[68px] space-y-1 rounded border border-flow-800 bg-flow-900 p-2">
          {!!e.data.actual && (
            <div>
              <p className="font-mono text-[9px] uppercase tracking-wider text-flow-600 mb-0.5">Agent response</p>
              <p className="font-mono text-[10px] text-flow-300 whitespace-pre-wrap break-words leading-relaxed">{String(e.data.actual)}</p>
            </div>
          )}
          {!!e.data.rationale && (
            <div>
              <p className="font-mono text-[9px] uppercase tracking-wider text-flow-600 mb-0.5">Judge rationale</p>
              <p className="font-mono text-[10px] text-flow-400 whitespace-pre-wrap break-words leading-relaxed">{String(e.data.rationale)}</p>
            </div>
          )}
          {!!e.data.content && !e.data.actual && (
            <div>
              <p className="font-mono text-[9px] uppercase tracking-wider text-flow-600 mb-0.5">Patch content</p>
              <p className="font-mono text-[10px] text-flow-300 whitespace-pre-wrap break-words leading-relaxed">{String(e.data.content)}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function LiveEventFeed({ events }: { events: TrainingEvent[] }) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  if (events.length === 0) {
    return (
      <div className="mt-3 rounded-md bg-flow-950 px-3 py-2.5">
        <p className="font-mono text-[10px] text-flow-600 animate-pulse">Waiting for events…</p>
      </div>
    )
  }

  return (
    <div className="mt-3 max-h-64 overflow-y-auto rounded-md border border-flow-800 bg-flow-950 p-2 space-y-0.5">
      <p className="mb-1.5 font-mono text-[10px] uppercase tracking-wider text-flow-600">Live log</p>
      {events.map((e) => (
        <EventRow key={e.id} event={e} />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}

function RunCard({ run, defaultOpen, skillId, onRunUpdated }: { run: TrainingRun; defaultOpen?: boolean; skillId: string; onRunUpdated?: (runId: string) => void }) {
  const [open, setOpen] = useState(defaultOpen ?? false)
  const date = new Date(run.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  const isActive = run.status === 'running' || run.status === 'pending'
  const events = useTrainingEvents(skillId, run.id, isActive && open)

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
          {isActive && <LiveEventFeed events={events} />}
          <GateVerdict run={run} skillId={skillId} onOverride={() => onRunUpdated?.(run.id)} />
          <EpochTimeline run={run} />
          <ItemScores items={latestItemScores(run)} />
          {(run.patches ?? []).length > 0 && <PatchList patches={run.patches!} />}
          {run.original_content && run.candidate_content && (
            <SkillDiff original={run.original_content} candidate={run.candidate_content} />
          )}
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

export function SkillTrainingPanel({ skillId, skillName, agentId, workspaceId, trainingMode, initialOpen }: Props) {
  const { runs, loading, reload, startPolling, forceReloadRun } = useSkillTrainingRuns(skillId)
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
  const goldenSets = useGoldenSets()
  const [selectedSet, setSelectedSet] = useState<string>('')
  const [showDatasetPreview, setShowDatasetPreview] = useState(false)
  const previewSetId = selectedSet || (goldenSets[0]?.id ?? null)
  const { items: previewItems, loading: previewLoading } = useGoldenSetItems(
    showDatasetPreview ? previewSetId : null
  )

  async function handleTrainNow() {
    await start(selectedSet || null)
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

          {/* Dataset picker */}
          <div className="flex flex-col gap-1.5 pl-9">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] uppercase tracking-wider text-flow-600">Dataset</span>
              <select
                value={selectedSet}
                onChange={(e) => setSelectedSet(e.target.value)}
                className="h-7 flex-1 min-w-0 rounded border border-flow-700 bg-flow-800 px-2 font-mono text-[11px] text-flow-300 focus:border-flow-violet focus:outline-none"
              >
                <option value="">Auto (first set)</option>
                {goldenSets.map((s) => (
                  <option key={s.id} value={s.id}>{s.name} ({s.item_count})</option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => setShowDatasetPreview(v => !v)}
                title="Preview dataset items"
                className={cn(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded border transition-colors",
                  showDatasetPreview
                    ? "border-flow-violet/50 bg-flow-violet/10 text-flow-violet"
                    : "border-flow-700 bg-flow-800 text-flow-500 hover:text-flow-300"
                )}
              >
                <Eye className="h-3.5 w-3.5" />
              </button>
            </div>

            {showDatasetPreview && (
              <div className="rounded-lg border border-flow-700/50 bg-flow-950 p-2.5 space-y-2">
                <div className="flex items-center gap-1.5">
                  <BookOpen className="h-3 w-3 text-flow-500 shrink-0" />
                  <span className="font-mono text-[10px] text-flow-500 uppercase tracking-wider">
                    {selectedSet
                      ? goldenSets.find(s => s.id === selectedSet)?.name
                      : `Auto — ${goldenSets[0]?.name ?? 'first set'}`}
                  </span>
                </div>
                {previewLoading ? (
                  <div className="flex justify-center py-2">
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-flow-600" />
                  </div>
                ) : previewItems.length === 0 ? (
                  <p className="font-mono text-[10px] text-flow-600">No items in this dataset.</p>
                ) : (
                  <div className="space-y-2">
                    {previewItems.slice(0, 3).map((item) => (
                      <div key={item.id} className="rounded border border-flow-800 bg-flow-900 p-2 space-y-1">
                        <div className="flex items-start gap-1.5">
                          <span className="shrink-0 font-mono text-[9px] text-flow-600 mt-0.5">IN</span>
                          <p className="font-mono text-[10px] text-flow-300 line-clamp-2 leading-tight">
                            {item.input_text}
                          </p>
                        </div>
                        <div className="flex items-start gap-1.5">
                          <span className="shrink-0 font-mono text-[9px] text-emerald-600 mt-0.5">OK</span>
                          <p className="font-mono text-[10px] text-emerald-400/80 line-clamp-1 leading-tight">
                            {item.expected_output.slice(0, 120)}{item.expected_output.length > 120 ? '…' : ''}
                          </p>
                        </div>
                        {item.scoring_criteria && (
                          <p className="font-mono text-[9px] text-flow-600 line-clamp-1 italic pl-5">
                            ↳ {item.scoring_criteria}
                          </p>
                        )}
                      </div>
                    ))}
                    {previewItems.length > 3 && (
                      <p className="font-mono text-[10px] text-flow-600 text-right">
                        +{previewItems.length - 3} more items
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

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
            <span className="font-semibold text-flow-500 block mb-1">How it works:</span>
            1. In the Run page, mark good responses as &quot;Golden&quot;<br />
            2. Select a dataset above (defines scoring criteria)<br />
            3. Click &quot;Train now&quot; — ReflACT edits the skill prompt<br />
            4. Changes only apply if eval score improves
          </p>
        </div>
      )}

      {!loading && runs.length > 0 && (
        <div className="space-y-2">
          <p className="px-0.5 font-mono text-[10px] uppercase tracking-wider text-flow-500">
            Training history · {runs.length} run{runs.length !== 1 ? 's' : ''}
          </p>
          {runs.slice(0, 6).map((run, i) => (
            <RunCard
              key={run.id}
              run={run}
              skillId={skillId}
              onRunUpdated={forceReloadRun}
              defaultOpen={
                (i === 0 && !!initialOpen) ||
                (i === 0 && (run.status === 'running' || run.status === 'pending' || run.status === 'failed'))
              }
            />
          ))}
        </div>
      )}
    </div>
  )
}
