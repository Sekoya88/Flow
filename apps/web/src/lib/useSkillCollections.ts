'use client'
import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'

export type CollectionSkill = { path: string; name: string }
export type Collection = {
  id: string
  name: string
  description: string
  repo: string
  category: string
  skill_count: number
  skills: CollectionSkill[]
}
export type ImportStep = {
  path: string
  name: string
  status: 'installed' | 'skipped' | 'error'
  reason: string
  skill_id?: string | null
  category?: string | null
}
export type ImportResult = {
  collection_id: string
  installed: number
  skipped: number
  errors: number
  steps: ImportStep[]
}

export function useCollections() {
  const [collections, setCollections] = useState<Collection[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let active = true
    apiFetch<{ collections: Collection[] }>('/api/v1/skills/collections')
      .then((d) => active && setCollections(d.collections))
      .catch((e) => active && setError(String(e)))
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [])
  return { collections, loading, error }
}

export function useImportCollection(workspaceId: string | undefined) {
  const [busyId, setBusyId] = useState<string | null>(null)
  const [results, setResults] = useState<Record<string, ImportResult>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const importCollection = useCallback(
    async (collectionId: string) => {
      if (!workspaceId) return
      setBusyId(collectionId)
      setErrors((e) => ({ ...e, [collectionId]: '' }))
      try {
        const res = await apiFetch<ImportResult>(
          `/api/v1/skills/collections/${collectionId}/import`,
          { method: 'POST', json: { workspace_id: workspaceId } },
        )
        setResults((r) => ({ ...r, [collectionId]: res }))
      } catch (e) {
        setErrors((er) => ({ ...er, [collectionId]: String(e) }))
      } finally {
        setBusyId(null)
      }
    },
    [workspaceId],
  )
  return { importCollection, busyId, results, errors }
}
