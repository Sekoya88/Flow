'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { OnboardingQuestionnaire } from '@/components/preferences/OnboardingQuestionnaire'
import { useOnboardingStatus } from '@/lib/useOnboardingStatus'

const workspaceId = 'default'

export default function OnboardingProfilePage() {
  const router = useRouter()
  const { status, loading, error } = useOnboardingStatus(workspaceId)
  const [completedCount, setCompletedCount] = useState<number | null>(null)

  if (loading) {
    return <p>Checking setup status...</p>
  }

  if (error) {
    return <p>Failed to load setup status. Please refresh.</p>
  }

  if (completedCount !== null) {
    return <p>Setup complete! {completedCount} preferences added.</p>
  }

  if (status?.completed) {
    return (
      <div>
        <p>Setup already complete. {status.preference_count} preferences configured.</p>
        <button onClick={() => router.push('/settings/profile')}>Go to profile settings</button>
      </div>
    )
  }

  return (
    <OnboardingQuestionnaire
      workspaceId={workspaceId}
      onComplete={(count) => setCompletedCount(count)}
      onDismiss={() => router.push('/settings/profile')}
    />
  )
}
