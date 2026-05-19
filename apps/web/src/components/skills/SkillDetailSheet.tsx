'use client'
import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, GitBranch, History, Loader2, Play, Sparkles } from 'lucide-react'
import { SkillDiffView } from '@/components/agents/SkillDiffView'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { SkillCatalogRow } from '@/lib/useSkillsCatalog'
import { useSkillHistory } from '@/lib/useSkillHistory'
import { useSkillUsage, type UsageDay } from '@/lib/useSkillUsage'
import { SkillPlayground } from './SkillPlayground'

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
  initialTab?: 'overview' | 'versions' | 'playground'
  onOpenChange: (open: boolean) => void
  onActivated?: () => void
}

export function SkillDetailSheet({
  skill,
  initialTab = 'overview',
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

  const handleActivate = async (id: string) => {
    await activate(id)
    onActivated?.()
  }

  return (
    <Sheet open={skill !== null} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-2xl border-l border-flow-800 p-0"
      >
        {skill && (
          <div className="flex h-full flex-col">
            <SheetHeader className="border-b border-flow-800 px-6 py-5">
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

            <Tabs value={tab} onValueChange={setTab} className="flex flex-1 flex-col">
              <div className="px-6 pt-3">
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
                </TabsList>
              </div>

              <TabsContent value="overview" className="flex-1">
                <ScrollArea className="h-full">
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
                </ScrollArea>
              </TabsContent>

              <TabsContent value="versions" className="flex-1">
                <ScrollArea className="h-full">
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
                </ScrollArea>
              </TabsContent>

              <TabsContent value="playground" className="flex-1">
                <ScrollArea className="h-full">
                  <div className="p-6">
                    <SkillPlayground skillId={skill.id} triggers={skill.triggers} />
                  </div>
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
