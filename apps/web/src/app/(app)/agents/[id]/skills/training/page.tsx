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

      {/* Workflow guide */}
      <div className="rounded-xl border border-flow-800 bg-flow-950 p-4">
        <p className="font-mono text-[10px] uppercase tracking-wider text-flow-500 mb-3">How training works</p>
        <div className="grid grid-cols-3 gap-4">
          {[
            {
              step: '1',
              label: 'Mark Golden',
              detail: 'In the Run page, mark good agent responses as "Golden" to build your training dataset.',
            },
            {
              step: '2',
              label: 'Select Dataset',
              detail: 'Each skill trains on a golden set — test cases with input/expected-output pairs and scoring criteria.',
            },
            {
              step: '3',
              label: 'Train & Gate',
              detail: 'ReflACT edits the skill prompt across epochs. Changes only apply if the eval score improves.',
            },
          ].map(({ step, label, detail }) => (
            <div key={step} className="flex gap-3">
              <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-flow-700 bg-flow-900 font-mono text-[11px] text-flow-400">
                {step}
              </div>
              <div>
                <p className="font-mono text-[11px] font-semibold text-flow-200">{label}</p>
                <p className="mt-0.5 text-[10px] leading-relaxed text-flow-500">{detail}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

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
