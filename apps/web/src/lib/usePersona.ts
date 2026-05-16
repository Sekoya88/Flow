'use client'
import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'

export interface Persona {
  id: string
  workspace_id: string
  user_id: string
  content_md: string
  version: number
  derived_from: Record<string, unknown>
  created_at: string
  updated_at: string
}

interface PersonaResponse {
  persona: Persona | null
}

export function usePersona(workspaceId: string | undefined) {
  const [persona, setPersona] = useState<Persona | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<'save' | 'regenerate' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!workspaceId) return
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ workspace_id: workspaceId })
      const res = await apiFetch<PersonaResponse>(`/api/v1/personas/me?${params}`)
      setPersona(res.persona)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load persona')
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  useEffect(() => { load() }, [load])

  const save = useCallback(async (content_md: string) => {
    if (!workspaceId) return
    setBusy('save')
    setError(null)
    try {
      const res = await apiFetch<PersonaResponse>('/api/v1/personas/me', {
        method: 'PUT',
        json: { workspace_id: workspaceId, content_md },
      })
      setPersona(res.persona)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save persona')
    } finally {
      setBusy(null)
    }
  }, [workspaceId])

  const regenerate = useCallback(async () => {
    if (!workspaceId) return
    setBusy('regenerate')
    setError(null)
    try {
      const res = await apiFetch<PersonaResponse>('/api/v1/personas/me/regenerate', {
        method: 'POST',
        json: { workspace_id: workspaceId },
      })
      setPersona(res.persona)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to regenerate persona')
    } finally {
      setBusy(null)
    }
  }, [workspaceId])

  return { persona, loading, busy, error, reload: load, save, regenerate }
}
