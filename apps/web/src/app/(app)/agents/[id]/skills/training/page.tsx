'use client'
import { useEffect, useRef, useState } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { FlowPageHeader } from '@/components/layout/FlowPageHeader'
import { SkillTrainingPanel } from '@/components/skills/SkillTrainingPanel'
import { apiFetch } from '@/lib/api'

type SkillRow = {
  id: string
  name: string
  metadata: Record<string, unknown>
}

type SkillsResponse = { skills: SkillRow[] }

export default function SkillTrainingPage() {
  const params = useParams<{ id: string }>()
  const agentId = params.id
  const router = useRouter()
  const searchParams = useSearchParams()
  const targetSkillId = searchParams.get('skill')

  const [skills, setSkills] = useState<SkillRow[]>([])
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const skillRefs = useRef<Record<string, HTMLDivElement | null>>({})

  useEffect(() => {
    if (!agentId) return
    // Same pattern as the Skills page: get workspace_id from /auth/me,
    // then fetch the agent's active skills. No single-agent detail endpoint exists.
    apiFetch<{ workspaces: { id: string }[] }>('/api/v1/auth/me')
      .then((me) => {
        const wsId = me.workspaces[0]?.id
        if (!wsId) return { skills: [] } as SkillsResponse
        setWorkspaceId(wsId)
        return apiFetch<SkillsResponse>(`/api/v1/skills?workspace_id=${wsId}&agent_id=${agentId}`)
      })
      .then(res => setSkills((res as SkillsResponse).skills ?? []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [agentId])

  useEffect(() => {
    if (!targetSkillId || loading) return
    const el = skillRefs.current[targetSkillId]
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [targetSkillId, loading])

  return (
    <div className="flex flex-col gap-6 p-6">
      <FlowPageHeader
        title="Skill Training"
        description="ReflACT optimizer — improve skills via bounded text edits."
        eyebrow={
          <button
            onClick={() => router.push(`/agents/${agentId}/skills`)}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Skills
          </button>
        }
      />

      {loading && (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Loading skills…</span>
        </div>
      )}

      {!loading && skills.length === 0 && (
        <p className="text-sm text-muted-foreground">No skills found. Create a skill first.</p>
      )}

      <div className="flex flex-col gap-4">
        {skills.map(skill => (
          <div key={skill.id} ref={el => { skillRefs.current[skill.id] = el }}>
            <SkillTrainingPanel
              skillId={skill.id}
              skillName={skill.name}
              agentId={agentId}
              workspaceId={workspaceId ?? ''}
              trainingMode={(skill.metadata?.training_mode as string | null) ?? null}
              initialOpen={skill.id === targetSkillId}
            />
          </div>
        ))}
      </div>
    </div>
  )
}
