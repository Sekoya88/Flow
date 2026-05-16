'use client'
import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'

export interface UsageDay {
  date: string
  count: number
}

interface UsageResponse {
  skill_id: string
  window_days: number
  data: UsageDay[]
}

export function useSkillUsage(skillId: string | undefined, windowDays = 7) {
  const [data, setData] = useState<UsageDay[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!skillId) {
      setData([])
      return
    }
    setLoading(true)
    apiFetch<UsageResponse>(`/api/v1/skills/${skillId}/usage?window=${windowDays}`)
      .then(res => setData(res.data ?? []))
      .catch(() => setData([]))
      .finally(() => setLoading(false))
  }, [skillId, windowDays])

  return { data, loading }
}
