'use client'
import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'

type WorkspaceMeta = { id: string }

let cached: string | null = null
let inflight: Promise<string | null> | null = null

async function fetchWorkspaceId(): Promise<string | null> {
  if (cached) return cached
  if (inflight) return inflight
  inflight = apiFetch<{ workspaces: WorkspaceMeta[] }>('/api/v1/auth/me')
    .then((m) => {
      const id = m.workspaces?.[0]?.id ?? null
      cached = id
      return id
    })
    .catch(() => null)
    .finally(() => {
      inflight = null
    })
  return inflight
}

export function useWorkspaceId(): { workspaceId: string | null; loading: boolean } {
  const [workspaceId, setWorkspaceId] = useState<string | null>(cached)
  const [loading, setLoading] = useState<boolean>(!cached)

  useEffect(() => {
    if (cached) return
    let active = true
    setLoading(true)
    fetchWorkspaceId()
      .then((id) => {
        if (active) setWorkspaceId(id)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  return { workspaceId, loading }
}
