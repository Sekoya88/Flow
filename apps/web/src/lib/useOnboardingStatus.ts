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

  useEffect(() => {
    if (!workspaceId) return
    apiFetch<OnboardingStatus>(
      `/api/v1/preferences/onboarding-status?workspace_id=${workspaceId}`
    )
      .then(setStatus)
      .finally(() => setLoading(false))
  }, [workspaceId])

  return { status, loading }
}
