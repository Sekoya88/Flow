'use client'
import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'

export interface SkillVersionRow {
  id: string
  version: number
  content_md: string
  active: boolean
  created_at: string
}

interface HistoryResponse {
  versions: SkillVersionRow[]
}

export function useSkillHistory(agentId: string | undefined, name: string | undefined) {
  const [versions, setVersions] = useState<SkillVersionRow[]>([])
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!agentId || !name) {
      setVersions([])
      return
    }
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ agent_id: agentId, name })
      const res = await apiFetch<HistoryResponse>(`/api/v1/skills/history?${params}`)
      setVersions(res.versions ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load history')
    } finally {
      setLoading(false)
    }
  }, [agentId, name])

  useEffect(() => { load() }, [load])

  const activate = useCallback(async (skillId: string) => {
    setBusy(skillId)
    setError(null)
    try {
      await apiFetch(`/api/v1/skills/${skillId}/activate`, { method: 'POST' })
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to activate version')
    } finally {
      setBusy(null)
    }
  }, [load])

  return { versions, loading, busy, error, reload: load, activate }
}
