'use client'
import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'

export interface OnboardingStatus {
  completed: boolean
  preference_count: number
}

export function useOnboardingStatus(workspaceId: string) {
  const [status, setStatus] = useState<OnboardingStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!workspaceId) return
    apiFetch<OnboardingStatus>(
      `/api/v1/preferences/onboarding-status?workspace_id=${workspaceId}`
    )
      .then(setStatus)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load status'))
      .finally(() => setLoading(false))
  }, [workspaceId])

  return { status, loading, error }
}
