'use client'
import { useMemo, useState } from 'react'
import { Layers, Loader2, Plus, Search, Sparkles, Workflow } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { CategorySection } from '@/components/skills/CategorySection'
import { CreateSkillSheet } from '@/components/skills/CreateSkillSheet'
import { SkillDetailSheet } from '@/components/skills/SkillDetailSheet'
import { SkillHubCard } from '@/components/skills/SkillHubCard'
import { useSkillsCatalog, type SkillCatalogRow } from '@/lib/useSkillsCatalog'
import { useWorkspaceId } from '@/lib/useWorkspace'

type SortKey = 'score' | 'recent' | 'runs'

const CATEGORY_ORDER = ['Research', 'Code', 'Communication', 'Analysis', 'Memory', 'Planning', 'General']

export default function SkillsHubPage() {
  const { workspaceId, loading: wsLoading } = useWorkspaceId()
  const [search, setSearch] = useState('')
  const [agentFilter, setAgentFilter] = useState<string>('all')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [sort, setSort] = useState<SortKey>('score')
  const [selected, setSelected] = useState<SkillCatalogRow | null>(null)
  const [initialTab, setInitialTab] = useState<'overview' | 'versions' | 'playground'>('overview')
  const [createOpen, setCreateOpen] = useState(false)

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

  const categoryOptions = useMemo(() => {
    const seen = new Set<string>()
    for (const s of skills) seen.add(s.category || 'General')
    return [...seen].sort((a, b) => {
      const ia = CATEGORY_ORDER.indexOf(a)
      const ib = CATEGORY_ORDER.indexOf(b)
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
    })
  }, [skills])

  const sorted = useMemo(() => {
    const copy = [...skills]
    if (sort === 'recent') copy.sort((a, b) => b.created_at.localeCompare(a.created_at))
    else if (sort === 'runs') copy.sort((a, b) => b.use_count - a.use_count)
    else copy.sort((a, b) => b.score - a.score)
    return copy
  }, [skills, sort])

  const visible = useMemo(() => {
    if (categoryFilter === 'all') return sorted
    return sorted.filter(s => (s.category || 'General') === categoryFilter)
  }, [sorted, categoryFilter])

  // Group by category only when not searching/filtering
  const isGrouped = !search.trim() && categoryFilter === 'all' && sort === 'score'

  const grouped = useMemo(() => {
    if (!isGrouped) return null
    const map = new Map<string, SkillCatalogRow[]>()
    for (const s of visible) {
      const cat = s.category || 'General'
      if (!map.has(cat)) map.set(cat, [])
      map.get(cat)!.push(s)
    }
    return [...map.entries()].sort(([a], [b]) => {
      const ia = CATEGORY_ORDER.indexOf(a)
      const ib = CATEGORY_ORDER.indexOf(b)
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
    })
  }, [isGrouped, visible])

  const openSkill = (skill: SkillCatalogRow) => { setInitialTab('overview'); setSelected(skill) }
  const tryRun = (skill: SkillCatalogRow) => { setInitialTab('playground'); setSelected(skill) }

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
          <Sparkles className="h-4 w-4 text-flow-violet" />
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-flow-violet/80">
            Skills Hub
          </span>
        </div>
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">
            Browse, version & test every skill
          </h1>
          <div className="flex items-center gap-3">
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
            <Button
              size="sm"
              onClick={() => setCreateOpen(true)}
              className="gap-1.5 h-8 text-xs"
            >
              <Plus className="h-3.5 w-3.5" />
              New Skill
            </Button>
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          Every active skill across every agent. Click any card to inspect versions,
          compare a prior version against the active one, or run it against a sample prompt.
        </p>
      </header>

      {/* Controls */}
      <section className="flow-card flex flex-wrap items-center gap-3 rounded-[6px] border border-flow-800 p-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground/60" />
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name or description…"
            className="pl-9"
          />
        </div>
        <Select value={agentFilter} onValueChange={v => setAgentFilter(v ?? 'all')}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="All agents" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All agents</SelectItem>
            {agentOptions.map(([id, name]) => (
              <SelectItem key={id} value={id}>{name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={categoryFilter} onValueChange={v => setCategoryFilter(v ?? 'all')}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="All categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            {categoryOptions.map(c => (
              <SelectItem key={c} value={c}>{c}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={sort} onValueChange={v => v && setSort(v as SortKey)}>
          <SelectTrigger className="w-[140px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="score">Sort: score</SelectItem>
            <SelectItem value="runs">Sort: runs</SelectItem>
            <SelectItem value="recent">Sort: recent</SelectItem>
          </SelectContent>
        </Select>
      </section>

      {/* Skills list */}
      {loading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading skills…
        </div>
      )}
      {error && <div className="text-sm text-destructive">{error}</div>}

      {!loading && visible.length === 0 && (
        <div className="flow-card rounded-[6px] border border-flow-800 p-10 text-center text-sm text-muted-foreground">
          No skills match the current filters.
        </div>
      )}

      {!loading && visible.length > 0 && (
        isGrouped && grouped ? (
          <div className="space-y-8">
            {grouped.map(([cat, catSkills]) => (
              <CategorySection
                key={cat}
                category={cat}
                skills={catSkills}
                onOpen={openSkill}
                onTry={tryRun}
              />
            ))}
          </div>
        ) : (
          <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {visible.map(skill => (
              <SkillHubCard key={skill.id} skill={skill} onOpen={openSkill} onTry={tryRun} />
            ))}
          </section>
        )
      )}

      <SkillDetailSheet
        skill={selected}
        initialTab={initialTab}
        onOpenChange={o => !o && setSelected(null)}
        onActivated={reload}
      />

      <CreateSkillSheet
        open={createOpen}
        workspaceId={workspaceId}
        onOpenChange={setCreateOpen}
        onCreated={reload}
      />
    </div>
  )
}
