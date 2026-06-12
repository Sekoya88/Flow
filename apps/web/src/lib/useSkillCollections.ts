'use client'
import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { apiFetch } from '@/lib/api'

export type GeneratedItem = {
  input_text: string
  expected_output: string
  scoring_criteria: string
  rationale: string
}
export type GenerateResult = {
  set_id: string
  set_name: string
  skill_id: string
  model: string
  prompt_used: string
  items: GeneratedItem[]
}

export function useGenerateDataset(skillId: string) {
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<GenerateResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const generate = useCallback(
    async (n = 5) => {
      setBusy(true)
      setError(null)
      try {
        const res = await apiFetch<GenerateResult>(`/api/v1/skills/${skillId}/generate-dataset`, {
          method: 'POST',
          json: { n },
        })
        setResult(res)
        return res
      } catch (e) {
        setError(String(e))
        return null
      } finally {
        setBusy(false)
      }
    },
    [skillId],
  )
  return { generate, busy, result, error }
}

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
        if (res.errors > 0) {
          toast.warning(`Import: ${res.installed} installed, ${res.errors} failed`)
        } else {
          toast.success(`Import: ${res.installed} installed, ${res.skipped} skipped`)
        }
      } catch (e) {
        setErrors((er) => ({ ...er, [collectionId]: String(e) }))
        toast.error('Collection import failed')
      } finally {
        setBusyId(null)
      }
    },
    [workspaceId],
  )
  return { importCollection, busyId, results, errors }
}
