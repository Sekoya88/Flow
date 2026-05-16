'use client'
import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'

export interface SkillCatalogRow {
  id: string
  agent_id: string
  agent_name: string
  name: string
  version: number
  description: string
  triggers: string[]
  allowed_tools: string[]
  metadata: Record<string, unknown>
  score: number
  use_count: number
  created_at: string
}

interface CatalogResponse {
  skills: SkillCatalogRow[]
}

interface UseCatalogOptions {
  agentId?: string
  q?: string
}

export function useSkillsCatalog(
  workspaceId: string | undefined,
  opts: UseCatalogOptions = {},
) {
  const [skills, setSkills] = useState<SkillCatalogRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { agentId, q } = opts

  const load = useCallback(async () => {
    if (!workspaceId) return
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ workspace_id: workspaceId })
      if (agentId) params.set('agent_id', agentId)
      if (q && q.trim()) params.set('q', q.trim())
      const res = await apiFetch<CatalogResponse>(`/api/v1/skills/catalog?${params}`)
      setSkills(res.skills ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load skills')
    } finally {
      setLoading(false)
    }
  }, [workspaceId, agentId, q])

  useEffect(() => { load() }, [load])

  return { skills, loading, error, reload: load }
}
