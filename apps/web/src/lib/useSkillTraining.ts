'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import { apiFetch } from '@/lib/api'

export interface TrainingEpoch {
  epoch: number
  eval_score: number
  baseline_score: number
  accepted: boolean
  patch_count: number
  created_at: string
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

  const start = useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      await apiFetch(`/api/v1/skills/${skillId}/train`, {
        method: 'POST',
        json: { agent_id: agentId, workspace_id: workspaceId, edit_budget: 5, max_epochs: 3 },
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
