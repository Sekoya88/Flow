'use client'
import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '@/lib/api'
import type { WorkspaceGraph, NodeType } from './types'

interface UseWorkspaceGraphOptions {
  workspaceId: string
  types?: NodeType[]
  since?: string
}

interface UseWorkspaceGraphResult {
  data: WorkspaceGraph | null
  loading: boolean
  error: string | null
  refetch: () => void
}

export function useWorkspaceGraph({
  workspaceId,
  types,
  since = '30d',
}: UseWorkspaceGraphOptions): UseWorkspaceGraphResult {
  const [data, setData] = useState<WorkspaceGraph | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  const refetch = useCallback(() => setTick(t => t + 1), [])

  useEffect(() => {
    if (!workspaceId) return
    setLoading(true)
    setError(null)

    const params = new URLSearchParams({ since })
    if (types?.length) params.set('types', types.join(','))

    apiFetch<WorkspaceGraph>(`/api/graph/workspace/${workspaceId}?${params}`)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [workspaceId, since, tick]) // eslint-disable-line react-hooks/exhaustive-deps

  return { data, loading, error, refetch }
}
