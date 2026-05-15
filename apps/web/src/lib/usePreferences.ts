'use client'
import { useEffect, useState, useCallback } from 'react'
import { apiFetch } from '@/lib/api'

export interface Preference {
  id: string
  class: string
  value: string
  score: number
  status: 'candidate' | 'provisional' | 'active'
  pinned: boolean
  agent_id: string | null
  last_reinforced_at: string
  created_at: string
}

interface PreferencesData {
  global: Preference[]
  agent_specific: Preference[]
}

export function usePreferences(workspaceId: string, agentId?: string) {
  const [data, setData] = useState<PreferencesData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!workspaceId) return
    setLoading(true)
    try {
      const params = new URLSearchParams({ workspace_id: workspaceId })
      if (agentId) params.set('agent_id', agentId)
      const result = await apiFetch<PreferencesData>(`/api/v1/preferences?${params}`)
      setData(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load preferences')
    } finally {
      setLoading(false)
    }
  }, [workspaceId, agentId])

  useEffect(() => { load() }, [load])

  const patchPreference = useCallback(async (id: string, action: string) => {
    await apiFetch(`/api/v1/preferences/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ action }),
    })
    await load()
  }, [load])

  const createPreference = useCallback(async (
    cls: string, value: string, agentId?: string
  ) => {
    await apiFetch('/api/v1/preferences', {
      method: 'POST',
      body: JSON.stringify({
        workspace_id: workspaceId,
        class: cls,
        value,
        ...(agentId ? { agent_id: agentId } : {}),
      }),
    })
    await load()
  }, [workspaceId, load])

  const deletePreference = useCallback(async (id: string) => {
    await apiFetch(`/api/v1/preferences/${id}`, { method: 'DELETE' })
    await load()
  }, [load])

  return { data, loading, error, reload: load, patchPreference, createPreference, deletePreference }
}
