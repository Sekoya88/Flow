'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import { apiFetch } from '@/lib/api'

export interface TrainingEvent {
  id: string
  stage: string  // 'epoch' | 'rollout' | 'reflect' | 'select' | 'update' | 'evaluate'
  kind: string   // 'stage_start' | 'item_result' | 'patch_proposed' | 'analysis' | 'summary' | 'score' | 'error'
  message: string
  data?: Record<string, unknown>
  created_at: string
}

export interface ItemScore {
  item_id: string
  input: string
  baseline_score: number
  candidate_score: number
  delta: number
}

export interface TrainingEpoch {
  epoch: number
  eval_score: number
  baseline_score: number
  accepted: boolean
  patch_count: number
  created_at: string
  item_scores?: ItemScore[] | null
}

export interface GoldenSetSummary {
  id: string
  name: string
  item_count: number
}

export interface TrainingPatch {
  op: string             // "replace" | "append" | "insert" | "delete"
  target: string         // section heading
  content: string | null
  impact_score: number | null
  applied: boolean
  rejected: boolean
}

export interface TrainingRun {
  id: string
  status: string       // "pending" | "running" | "done" | "failed"
  epoch: number
  baseline_score: number | null
  best_score: number | null
  accepted: boolean | null
  created_at: string
  error_message?: string | null
  epochs?: TrainingEpoch[]
  patches?: TrainingPatch[]
  patches_applied?: number
  patches_rejected?: number
  original_content?: string | null
  candidate_content?: string | null
}

interface TrainingRunsResponse {
  runs: TrainingRun[]
}

// Poll training runs for a skill. Stops polling when all runs are done/failed.
// For done/accepted runs, also fetches the detail (patches + diff content).
export function useSkillTrainingRuns(skillId: string | undefined) {
  const [runs, setRuns] = useState<TrainingRun[]>([])
  const [loading, setLoading] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // Track which run IDs have already been enriched with detail data
  const enrichedRef = useRef<Set<string>>(new Set())

  const enrichRun = useCallback(async (run: TrainingRun): Promise<TrainingRun> => {
    if (!skillId) return run
    if (enrichedRef.current.has(run.id)) return run
    // Only fetch detail for terminal runs that have something to show
    if (run.status !== 'done' && run.status !== 'failed') return run
    try {
      const detail = await apiFetch<TrainingRun>(`/api/v1/skills/${skillId}/training-runs/${run.id}`)
      enrichedRef.current.add(run.id)
      return { ...run, ...detail }
    } catch {
      return run
    }
  }, [skillId])

  const load = useCallback(async () => {
    if (!skillId) return
    try {
      const res = await apiFetch<TrainingRunsResponse>(`/api/v1/skills/${skillId}/training-runs`)
      const rawRuns = res.runs ?? []

      // Enrich terminal runs with detail data (patches, content)
      const enriched = await Promise.all(rawRuns.map(enrichRun))
      setRuns(enriched)

      // Stop polling if no runs are active
      const hasActive = enriched.some(r => r.status === 'pending' || r.status === 'running')
      if (!hasActive && intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    } catch {
      // silently ignore
    }
  }, [skillId, enrichRun])

  const startPolling = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    intervalRef.current = setInterval(load, 3000)
  }, [load])

  useEffect(() => {
    setLoading(true)
    load().finally(() => setLoading(false))
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [load])

  return { runs, loading, reload: load, startPolling }
}

// Trigger a training run and start polling.
export function useStartTraining(
  skillId: string,
  agentId: string,
  workspaceId: string,
  onStarted: () => void,
) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const start = useCallback(async (goldenSetId?: string | null) => {
    setBusy(true)
    setError(null)
    try {
      await apiFetch(`/api/v1/skills/${skillId}/train`, {
        method: 'POST',
        json: {
          agent_id: agentId,
          workspace_id: workspaceId,
          edit_budget: 5,
          max_epochs: 3,
          ...(goldenSetId ? { golden_set_id: goldenSetId } : {}),
        },
      })
      onStarted()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start training')
    } finally {
      setBusy(false)
    }
  }, [skillId, agentId, workspaceId, onStarted])

  return { start, busy, error }
}

// List the workspace's golden sets so the user can pick which dataset to train on.
export function useGoldenSets() {
  const [sets, setSets] = useState<GoldenSetSummary[]>([])
  useEffect(() => {
    apiFetch<{ sets: GoldenSetSummary[] }>(`/api/v1/golden-sets`)
      .then((res) => setSets(res.sets ?? []))
      .catch(() => { /* ignore */ })
  }, [])
  return sets
}

// Toggle training_mode on a skill.
export function useTrainingModeToggle(skillId: string, onToggled: () => void) {
  const [busy, setBusy] = useState(false)

  const toggle = useCallback(async (enable: boolean) => {
    setBusy(true)
    try {
      await apiFetch(`/api/v1/skills/${skillId}`, {
        method: 'PATCH',
        json: { training_mode: enable ? 'react' : null },
      })
      onToggled()
    } catch {
      // silently ignore
    } finally {
      setBusy(false)
    }
  }, [skillId, onToggled])

  return { toggle, busy }
}

// Poll live COT events for an active training run. Stops when active=false.
export function useTrainingEvents(
  skillId: string | undefined,
  runId: string | undefined,
  active: boolean,
) {
  const [events, setEvents] = useState<TrainingEvent[]>([])
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async () => {
    if (!skillId || !runId) return
    try {
      const res = await apiFetch<{ events: TrainingEvent[] }>(
        `/api/v1/skills/${skillId}/training-runs/${runId}/events`,
      )
      setEvents(res.events ?? [])
    } catch { /* ignore */ }
  }, [skillId, runId])

  useEffect(() => {
    if (!active || !skillId || !runId) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
      return
    }
    void load()
    intervalRef.current = setInterval(load, 2000)
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [active, skillId, runId, load])

  return events
}
