'use client'
import { useState, useEffect } from 'react'
import { apiFetch } from '@/lib/api'
import type { EntityGraph, NodeType } from './types'

interface UseEntityGraphOptions {
  workspaceId: string
  nodeType: NodeType
  refId: string
  enabled?: boolean
}

interface UseEntityGraphResult {
  data: EntityGraph | null
  loading: boolean
  error: string | null
}

export function useEntityGraph({
  workspaceId,
  nodeType,
  refId,
  enabled = true,
}: UseEntityGraphOptions): UseEntityGraphResult {
  const [data, setData] = useState<EntityGraph | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled || !workspaceId || !refId) return
    setLoading(true)
    setError(null)

    const params = new URLSearchParams({ workspace_id: workspaceId })

    apiFetch<EntityGraph>(`/api/graph/entity/${nodeType}/${refId}?${params}`)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [workspaceId, nodeType, refId, enabled])

  return { data, loading, error }
}
