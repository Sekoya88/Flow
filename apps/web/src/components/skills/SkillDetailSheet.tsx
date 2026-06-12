'use client'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { BrainCircuit, CheckCircle2, GitBranch, History, Loader2, Play, Sparkles, Wand2 } from 'lucide-react'
import { SkillDiffView } from '@/components/agents/SkillDiffView'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import type { SkillCatalogRow } from '@/lib/useSkillsCatalog'
import { useSkillHistory } from '@/lib/useSkillHistory'
import { useSkillUsage, type UsageDay } from '@/lib/useSkillUsage'
import { SkillPlayground } from './SkillPlayground'
import { SkillTrainingPanel } from './SkillTrainingPanel'

function UsageSparkline({ data }: { data: UsageDay[] }) {
  if (data.length < 2) return null
  const max = Math.max(...data.map(d => d.count), 1)
  const w = 140
  const h = 32
  const pad = 3
  const step = (w - pad * 2) / (data.length - 1)
  const points = data
    .map((d, i) => {
      const x = pad + i * step
      const y = h - pad - ((d.count / max) * (h - pad * 2))
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline
        points={points}
        fill="none"
        stroke="var(--flow-violet)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.8}
      />
    </svg>
  )
}

interface SkillDetailSheetProps {
  skill: SkillCatalogRow | null
  initialTab?: 'overview' | 'versions' | 'playground' | 'train'
  workspaceId?: string
  onOpenChange: (open: boolean) => void
  onActivated?: () => void
}

export function SkillDetailSheet({
  skill,
  initialTab = 'overview',
  workspaceId,
  onOpenChange,
  onActivated,
}: SkillDetailSheetProps) {
  const [tab, setTab] = useState<string>(initialTab)
  useEffect(() => { setTab(initialTab) }, [initialTab, skill?.id])

  const { versions, loading, busy, error, activate } = useSkillHistory(
    skill?.agent_id,
    skill?.name,
  )
  const { data: usageData } = useSkillUsage(skill?.id)

  const activeVersion = useMemo(
    () => versions.find(v => v.active) ?? versions[0] ?? null,
    [versions],
  )
  const [selectedVid, setSelectedVid] = useState<string | null>(null)
  useEffect(() => {
    const firstInactive = versions.find(v => !v.active)
    setSelectedVid(firstInactive?.id ?? null)
  }, [versions])

  const selectedVersion = useMemo(
    () => versions.find(v => v.id === selectedVid) ?? null,
    [versions, selectedVid],
  )

  // Vibe-modify state
  type VibeState = 'idle' | 'streaming' | 'done' | 'error'
  const [vibePrompt, setVibePrompt] = useState('')
  const [vibeState, setVibeState] = useState<VibeState>('idle')
  const [vibeContent, setVibeContent] = useState('')
  const [vibeCandidateId, setVibeCandidateId] = useState<string | null>(null)
  const [vibeActivating, setVibeActivating] = useState(false)
  const [vibeActivated, setVibeActivated] = useState(false)
  const vibeScrollRef = useRef<HTMLPreElement>(null)

  useEffect(() => {
    if (vibeScrollRef.current) {
      vibeScrollRef.current.scrollTop = vibeScrollRef.current.scrollHeight
    }
  }, [vibeContent])

  useEffect(() => {
    setVibePrompt('')
    setVibeState('idle')
    setVibeContent('')
    setVibeCandidateId(null)
    setVibeActivated(false)
  }, [skill?.id])

  const handleVibeModify = useCallback(async () => {
    if (!skill || !vibePrompt.trim()) return
    setVibeState('streaming')
    setVibeContent('')
    setVibeCandidateId(null)
    setVibeActivated(false)

    try {
      const res = await fetch(`/api/v1/skills/${skill.id}/vibe-modify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('flow_token')}` },
        body: JSON.stringify({ prompt: vibePrompt }),
      })
      if (!res.body) throw new Error('no stream')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const ev = JSON.parse(line.slice(6))
            if (ev.token) setVibeContent(p => p + ev.token)
            if (ev.done && ev.skill_id) {
              setVibeCandidateId(ev.skill_id)
              setVibeState('done')
            }
          } catch { /* ignore */ }
        }
      }
    } catch {
      setVibeState('error')
    }
  }, [skill, vibePrompt])

  const handleVibeActivateNow = useCallback(async () => {
    if (!vibeCandidateId) return
    setVibeActivating(true)
    try {
      await fetch(`/api/v1/skills/${vibeCandidateId}/activate`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('flow_token')}` },
      })
      setVibeActivated(true)
      toast.success('New skill version activated')
      onActivated?.()
    } finally {
      setVibeActivating(false)
    }
  }, [vibeCandidateId, onActivated])

  const handleVibeSubmitReview = useCallback(async () => {
    if (!vibeCandidateId) return
    setVibeActivating(true)
    try {
      await fetch(`/api/v1/proposals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('flow_token')}` },
        body: JSON.stringify({ skill_candidate_id: vibeCandidateId, title: `Vibe edit: ${skill?.name}` }),
      }).catch(() => {})
      setVibeActivated(true)
      onActivated?.()
    } finally {
      setVibeActivating(false)
    }
  }, [vibeCandidateId, skill?.name, onActivated])

  const handleActivate = async (id: string) => {
    try {
      await activate(id)
      toast.success('Version activated')
      onActivated?.()
    } catch {
      toast.error('Failed to activate version')
    }
  }

  return (
    <Sheet open={skill !== null} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-2xl border-l border-flow-800 p-0 gap-0 overflow-hidden"
      >
        {skill && (
          <>
            <SheetHeader className="shrink-0 border-b border-flow-800 px-6 py-5">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-flow-violet" />
                <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-flow-violet/80">
                  Skill
                </span>
                <Badge variant="outline" className="font-mono text-[10px]">
                  v{skill.version}
                </Badge>
              </div>
              <SheetTitle className="font-mono text-lg tracking-tight">
                {skill.name}
              </SheetTitle>
              <p className="text-xs text-muted-foreground">
                Owned by <span className="text-foreground">{skill.agent_name}</span>
                {skill.description && ` — ${skill.description}`}
              </p>
            </SheetHeader>

            {/* Tabs root is display:contents — layout-transparent, only manages state */}
            <Tabs value={tab} onValueChange={setTab} className="contents">
              <div className="shrink-0 overflow-x-auto border-b border-flow-800/50 px-6 pt-3 pb-0">
                <TabsList>
                  <TabsTrigger value="overview">Overview</TabsTrigger>
                  <TabsTrigger value="versions">
                    <History className="mr-1 h-3.5 w-3.5" />
                    Versions
                  </TabsTrigger>
                  <TabsTrigger value="playground">
                    <Play className="mr-1 h-3.5 w-3.5" />
                    Playground
                  </TabsTrigger>
                  <TabsTrigger value="vibe">
                    <Wand2 className="mr-1 h-3.5 w-3.5" />
                    Vibe
                  </TabsTrigger>
                  <TabsTrigger value="train">
                    <BrainCircuit className="mr-1 h-3.5 w-3.5" />
                    Train
                  </TabsTrigger>
                </TabsList>
              </div>
            </Tabs>

            {/* Scrollable content — direct flex child of SheetContent (flex-col) */}
            <div className="flex-1 min-h-0 overflow-y-auto overflow-x-auto">
              {tab === 'overview' && (
                <div className="space-y-4 p-6">
                  {skill.triggers.length > 0 && (
                    <section>
                      <h4 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">
                        Triggers
                      </h4>
                      <div className="flex flex-wrap gap-1.5">
                        {skill.triggers.map((t, i) => (
                          <Badge key={`${t}-${i}`} variant="outline">
                            {t}
                          </Badge>
                        ))}
                      </div>
                    </section>
                  )}
                  {skill.allowed_tools.length > 0 && (
                    <section>
                      <h4 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">
                        Allowed tools
                      </h4>
                      <div className="flex flex-wrap gap-1.5">
                        {skill.allowed_tools.map((t, i) => (
                          <Badge
                            key={`${t}-${i}`}
                            variant="outline"
                            className="border-flow-violet/40 text-flow-violet"
                          >
                            {t}
                          </Badge>
                        ))}
                      </div>
                    </section>
                  )}
                  <section className="grid grid-cols-2 gap-3 pt-2">
                    <div className="flow-card rounded-lg border border-flow-800 p-3">
                      <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60">
                        Score
                      </div>
                      <div className="mt-1 font-mono text-sm text-foreground">
                        {skill.score.toFixed(2)}
                      </div>
                    </div>
                    <div className="flow-card rounded-lg border border-flow-800 p-3">
                      <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60">
                        Runs
                      </div>
                      <div className="mt-1 font-mono text-sm text-foreground">
                        {skill.use_count}
                      </div>
                    </div>
                  </section>
                  {usageData.length >= 2 && (
                    <section className="flow-card rounded-lg border border-flow-800 p-3">
                      <div className="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60">
                        Activity (7d)
                      </div>
                      <UsageSparkline data={usageData} />
                    </section>
                  )}
                </div>
              )}

              {tab === 'versions' && (
                <div className="space-y-4 p-6">
                  {loading && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Loading history…
                    </div>
                  )}
                  {error && (
                    <div className="text-xs text-destructive">{error}</div>
                  )}
                  {!loading && versions.length === 0 && (
                    <div className="text-xs text-muted-foreground">
                      No prior versions — this skill has only ever been saved once.
                    </div>
                  )}
                  {versions.length > 0 && (
                    <ul className="space-y-2">
                      {versions.map(v => (
                        <li
                          key={v.id}
                          className={`flex items-center justify-between gap-3 rounded-lg border px-3 py-2 transition-colors ${
                            v.id === selectedVid
                              ? 'border-flow-violet/60 bg-flow-violet/[0.04]'
                              : 'border-flow-800 hover:border-flow-800'
                          }`}
                        >
                          <button
                            type="button"
                            className="flex flex-1 items-center gap-3 text-left"
                            onClick={() => setSelectedVid(v.id)}
                          >
                            <Badge
                              variant="outline"
                              className={
                                v.active
                                  ? 'border-flow-violet/60 text-flow-violet'
                                  : 'border-flow-800 text-muted-foreground'
                              }
                            >
                              v{v.version}
                            </Badge>
                            {v.active && (
                              <span className="font-mono text-[10px] uppercase tracking-wider text-flow-violet">
                                active
                              </span>
                            )}
                            <span className="font-mono text-[11px] text-muted-foreground/70">
                              {new Date(v.created_at).toLocaleString()}
                            </span>
                          </button>
                          {!v.active && (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={busy !== null}
                              onClick={() => handleActivate(v.id)}
                            >
                              {busy === v.id ? (
                                <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
                              )}
                              Set active
                            </Button>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                  {activeVersion && selectedVersion && selectedVersion.id !== activeVersion.id && (
                    <section className="space-y-2 pt-2">
                      <h4 className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">
                        <GitBranch className="h-3 w-3" />
                        Compare with active
                      </h4>
                      <SkillDiffView
                        oldContent={selectedVersion.content_md}
                        newContent={activeVersion.content_md}
                        oldLabel={`v${selectedVersion.version}`}
                        newLabel={`v${activeVersion.version} (active)`}
                      />
                    </section>
                  )}
                </div>
              )}

              {tab === 'playground' && (
                <div className="p-6">
                  <SkillPlayground skillId={skill.id} triggers={skill.triggers} />
                </div>
              )}

              {tab === 'vibe' && (
                <div className="space-y-4 p-6">
                  <p className="text-xs text-muted-foreground">
                    Describe the change you want — the AI will generate a new version of this skill.
                  </p>
                  <Textarea
                    value={vibePrompt}
                    onChange={e => setVibePrompt(e.target.value)}
                    placeholder="e.g. Add an example for summarizing Slack threads, and make the output format use bullet points…"
                    rows={3}
                    className="resize-none text-sm"
                    disabled={vibeState === 'streaming'}
                  />
                  {vibeState === 'idle' && (
                    <Button size="sm" onClick={handleVibeModify} disabled={!vibePrompt.trim()} className="gap-1.5">
                      <Wand2 className="h-3.5 w-3.5" />
                      Generate modification
                    </Button>
                  )}
                  {vibeState === 'streaming' && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Generating…
                    </div>
                  )}
                  {(vibeState === 'streaming' || vibeState === 'done') && vibeContent && (
                    <pre
                      ref={vibeScrollRef}
                      className="max-h-80 overflow-y-auto rounded-[6px] border border-flow-800 bg-muted/20 p-4 font-mono text-xs leading-relaxed text-foreground/80 whitespace-pre-wrap"
                    >
                      {vibeContent}
                    </pre>
                  )}
                  {vibeState === 'done' && !vibeActivated && (
                    <div className="flex gap-2">
                      <Button size="sm" onClick={handleVibeActivateNow} disabled={vibeActivating} className="gap-1.5">
                        {vibeActivating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                        Activate now
                      </Button>
                      <Button size="sm" variant="outline" onClick={handleVibeSubmitReview} disabled={vibeActivating} className="gap-1.5 border-flow-800">
                        Submit for review
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => { setVibeState('idle'); setVibeContent('') }} className="text-muted-foreground">
                        Discard
                      </Button>
                    </div>
                  )}
                  {vibeState === 'done' && vibeActivated && (
                    <div className="flex items-center gap-1.5 text-xs text-emerald-400">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Version saved successfully
                    </div>
                  )}
                  {vibeState === 'error' && (
                    <p className="text-xs text-destructive">Generation failed. Check API key configuration.</p>
                  )}
                </div>
              )}

              {tab === 'train' && (
                workspaceId ? (
                  <div className="p-6">
                    <SkillTrainingPanel
                      skillId={skill.id}
                      skillName={skill.name}
                      agentId={skill.agent_id}
                      workspaceId={workspaceId}
                      trainingMode={null}
                    />
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2 p-6 text-center">
                    <BrainCircuit className="h-8 w-8 text-muted-foreground/30" />
                    <p className="text-sm text-muted-foreground">Workspace not available.</p>
                  </div>
                )
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
