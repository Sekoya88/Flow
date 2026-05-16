'use client'
import { useMemo, useState } from 'react'
import { Layers, Loader2, Search, Sparkles, Workflow } from 'lucide-react'
import { SkillDetailSheet } from '@/components/skills/SkillDetailSheet'
import { SkillHubCard } from '@/components/skills/SkillHubCard'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useSkillsCatalog, type SkillCatalogRow } from '@/lib/useSkillsCatalog'
import { useWorkspaceId } from '@/lib/useWorkspace'

type SortKey = 'score' | 'recent' | 'runs'

export default function SkillsHubPage() {
  const { workspaceId, loading: wsLoading } = useWorkspaceId()
  const [search, setSearch] = useState('')
  const [agentFilter, setAgentFilter] = useState<string>('all')
  const [sort, setSort] = useState<SortKey>('score')
  const [selected, setSelected] = useState<SkillCatalogRow | null>(null)
  const [initialTab, setInitialTab] = useState<'overview' | 'versions' | 'playground'>('overview')

  const { skills, loading, error, reload } = useSkillsCatalog(workspaceId ?? undefined, {
    agentId: agentFilter === 'all' ? undefined : agentFilter,
    q: search,
  })

  const agentOptions = useMemo(() => {
    const seen = new Map<string, string>()
    for (const s of skills) {
      if (!seen.has(s.agent_id)) seen.set(s.agent_id, s.agent_name)
    }
    return [...seen.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  }, [skills])

  const visible = useMemo(() => {
    const copy = [...skills]
    if (sort === 'recent') {
      copy.sort((a, b) => b.created_at.localeCompare(a.created_at))
    } else if (sort === 'runs') {
      copy.sort((a, b) => b.use_count - a.use_count)
    } else {
      copy.sort((a, b) => b.score - a.score)
    }
    return copy
  }, [skills, sort])

  const openSkill = (skill: SkillCatalogRow) => {
    setInitialTab('overview')
    setSelected(skill)
  }
  const tryRun = (skill: SkillCatalogRow) => {
    setInitialTab('playground')
    setSelected(skill)
  }

  if (wsLoading) {
    return (
      <div className="mx-auto flex max-w-2xl items-center justify-center gap-2 px-4 py-16 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>Loading workspace…</span>
      </div>
    )
  }
  if (!workspaceId) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-sm text-destructive">
        No workspace found. Sign in again.
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 pb-12 pt-6 animate-fade-in">
      {/* Header */}
      <header className="space-y-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-flow-brand" />
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-flow-brand/80">
            Skills Hub
          </span>
        </div>
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">
            Browse, version & test every skill
          </h1>
          <div className="flex items-center gap-3 font-mono text-[11px] text-muted-foreground">
            <span className="flex items-center gap-1">
              <Layers className="h-3 w-3" />
              {skills.length} active
            </span>
            <span className="flex items-center gap-1">
              <Workflow className="h-3 w-3" />
              {agentOptions.length} agents
            </span>
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          Every active skill across every agent. Click any card to inspect versions,
          compare a prior version against the active one, or run it against a sample prompt.
        </p>
      </header>

      {/* Controls */}
      <section className="surface-glass flex flex-wrap items-center gap-3 rounded-2xl border border-border/40 p-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground/60" />
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name or description…"
            className="pl-9"
          />
        </div>
        <Select value={agentFilter} onValueChange={(v) => setAgentFilter(v ?? 'all')}>
          <SelectTrigger className="w-[220px]">
            <SelectValue placeholder="All agents" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All agents</SelectItem>
            {agentOptions.map(([id, name]) => (
              <SelectItem key={id} value={id}>
                {name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={sort} onValueChange={(v) => v && setSort(v as SortKey)}>
          <SelectTrigger className="w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="score">Sort: score</SelectItem>
            <SelectItem value="runs">Sort: runs</SelectItem>
            <SelectItem value="recent">Sort: recent</SelectItem>
          </SelectContent>
        </Select>
      </section>

      {/* Grid */}
      {loading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading skills…
        </div>
      )}
      {error && <div className="text-sm text-destructive">{error}</div>}

      {!loading && visible.length === 0 && (
        <div className="surface-glass rounded-2xl border border-border/40 p-10 text-center text-sm text-muted-foreground">
          No skills match the current filters.
        </div>
      )}

      {!loading && visible.length > 0 && (
        <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visible.map(skill => (
            <SkillHubCard
              key={skill.id}
              skill={skill}
              onOpen={openSkill}
              onTry={tryRun}
            />
          ))}
        </section>
      )}

      <SkillDetailSheet
        skill={selected}
        initialTab={initialTab}
        onOpenChange={(o) => !o && setSelected(null)}
        onActivated={() => reload()}
      />
    </div>
  )
}
