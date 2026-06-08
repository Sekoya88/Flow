'use client'
import { useMemo, useState } from 'react'
import Link from 'next/link'
import {
  BarChart2,
  Brain,
  BrainCircuit,
  Calendar,
  Code2,
  Layers,
  Loader2,
  MessageSquare,
  Plus,
  Search,
  Sparkles,
  Store,
  Target,
  Workflow,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { CreateSkillSheet } from '@/components/skills/CreateSkillSheet'
import { SkillDetailSheet } from '@/components/skills/SkillDetailSheet'
import { SkillHubCard } from '@/components/skills/SkillHubCard'
import { useSkillsCatalog, type SkillCatalogRow } from '@/lib/useSkillsCatalog'
import { useWorkspaceId } from '@/lib/useWorkspace'
import { cn } from '@/lib/utils'

type SortKey = 'score' | 'recent' | 'runs'

const CATEGORY_ORDER = ['Research', 'Code', 'Communication', 'Analysis', 'Memory', 'Planning', 'General']

const CATEGORY_ICONS: Record<string, React.ElementType> = {
  Research: Search,
  Code: Code2,
  Communication: MessageSquare,
  Analysis: BarChart2,
  Memory: Brain,
  Planning: Target,
  General: Layers,
}

const CATEGORY_COLORS: Record<string, string> = {
  Research:      'text-sky-400 bg-sky-400/10 border-sky-400/20',
  Code:          'text-emerald-400 bg-emerald-400/10 border-emerald-400/20',
  Communication: 'text-amber-400 bg-amber-400/10 border-amber-400/20',
  Analysis:      'text-violet-400 bg-violet-400/10 border-violet-400/20',
  Memory:        'text-rose-400 bg-rose-400/10 border-rose-400/20',
  Planning:      'text-orange-400 bg-orange-400/10 border-orange-400/20',
  General:       'text-flow-400 bg-flow-400/10 border-flow-400/20',
}

export default function SkillsHubPage() {
  const { workspaceId, loading: wsLoading } = useWorkspaceId()
  const [search, setSearch] = useState('')
  const [agentFilter, setAgentFilter] = useState<string>('all')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [sort, setSort] = useState<SortKey>('score')
  const [selected, setSelected] = useState<SkillCatalogRow | null>(null)
  const [initialTab, setInitialTab] = useState<'overview' | 'versions' | 'playground' | 'train'>('overview')
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

  const sorted = useMemo(() => {
    const copy = [...skills]
    if (sort === 'recent') copy.sort((a, b) => b.created_at.localeCompare(a.created_at))
    else if (sort === 'runs') copy.sort((a, b) => b.use_count - a.use_count)
    else copy.sort((a, b) => b.score - a.score)
    return copy
  }, [skills, sort])

  // Counts per category (from all skills, not filtered)
  const categoryCounts = useMemo(() => {
    const m: Record<string, number> = {}
    for (const s of sorted) {
      const cat = s.category || 'General'
      m[cat] = (m[cat] ?? 0) + 1
    }
    return m
  }, [sorted])

  const sortedCategories = useMemo(() =>
    CATEGORY_ORDER.filter(c => (categoryCounts[c] ?? 0) > 0),
    [categoryCounts]
  )

  const visible = useMemo(() => {
    if (categoryFilter === 'all') return sorted
    return sorted.filter(s => (s.category || 'General') === categoryFilter)
  }, [sorted, categoryFilter])

  // Category overview: per-category preview (top 3 skill names)
  const categoryPreviews = useMemo(() => {
    const m: Record<string, SkillCatalogRow[]> = {}
    for (const s of sorted) {
      const cat = s.category || 'General'
      if (!m[cat]) m[cat] = []
      if (m[cat].length < 3) m[cat].push(s)
    }
    return m
  }, [sorted])

  const showOverview = categoryFilter === 'all' && !search.trim()

  const openSkill = (skill: SkillCatalogRow) => { setInitialTab('overview'); setSelected(skill) }
  const tryRun = (skill: SkillCatalogRow) => { setInitialTab('playground'); setSelected(skill) }
  const trainSkill = (skill: SkillCatalogRow) => { setInitialTab('train'); setSelected(skill) }

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
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 pb-12 pt-6">
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
            {categoryFilter === 'all' ? 'Browse, version & test every skill' : categoryFilter}
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
            <Link
              href="/skills/marketplace"
              className="inline-flex h-8 items-center gap-1.5 rounded-md border border-flow-700 bg-flow-900 px-3 font-mono text-xs text-flow-300 hover:bg-flow-800 hover:text-flow-100 transition-colors"
            >
              <Store className="h-3 w-3" />
              Import
            </Link>
            <Button size="sm" onClick={() => setCreateOpen(true)} className="gap-1.5 h-8 text-xs">
              <Plus className="h-3.5 w-3.5" />
              New Skill
            </Button>
          </div>
        </div>
      </header>

      {/* Search + controls */}
      <section className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground/60" />
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name or description…"
            className="pl-9"
          />
        </div>
        {agentOptions.length > 1 && (
          <Select value={agentFilter} onValueChange={v => setAgentFilter(v ?? 'all')}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="All agents" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All agents</SelectItem>
              {agentOptions.map(([id, name]) => (
                <SelectItem key={id} value={id}>{name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        {!showOverview && (
          <Select value={sort} onValueChange={v => v && setSort(v as SortKey)}>
            <SelectTrigger className="w-[130px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="score">By score</SelectItem>
              <SelectItem value="runs">By runs</SelectItem>
              <SelectItem value="recent">By recent</SelectItem>
            </SelectContent>
          </Select>
        )}
      </section>

      {/* Category pill strip */}
      {!loading && sortedCategories.length > 1 && (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setCategoryFilter('all')}
            className={cn(
              'rounded-full border px-3 py-1 font-mono text-[11px] font-medium transition-colors',
              categoryFilter === 'all'
                ? 'border-flow-violet bg-flow-violet/15 text-flow-violet'
                : 'border-flow-800 text-flow-500 hover:border-flow-600 hover:text-flow-200'
            )}
          >
            All
          </button>
          {sortedCategories.map(cat => {
            const Icon = CATEGORY_ICONS[cat] ?? Layers
            const active = categoryFilter === cat
            return (
              <button
                key={cat}
                onClick={() => setCategoryFilter(cat)}
                className={cn(
                  'flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-[11px] font-medium transition-colors',
                  active
                    ? cn(CATEGORY_COLORS[cat] ?? CATEGORY_COLORS.General, 'border-current')
                    : 'border-flow-800 text-flow-500 hover:border-flow-600 hover:text-flow-200'
                )}
              >
                <Icon className="h-3 w-3" />
                {cat}
                <span className="opacity-60">{categoryCounts[cat]}</span>
              </button>
            )
          })}
        </div>
      )}

      {/* Loading / error */}
      {loading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading skills…
        </div>
      )}
      {error && <div className="text-sm text-destructive">{error}</div>}

      {/* Category overview grid */}
      {!loading && showOverview && sortedCategories.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sortedCategories.map(cat => {
            const Icon = CATEGORY_ICONS[cat] ?? Layers
            const colorClass = CATEGORY_COLORS[cat] ?? CATEGORY_COLORS.General
            const previews = categoryPreviews[cat] ?? []
            const count = categoryCounts[cat] ?? 0
            const firstSkill = previews[0] ?? null
            return (
              <div
                key={cat}
                className="group flex flex-col gap-3 rounded-[8px] border border-flow-800 bg-flow-950 p-5 text-left transition-all duration-150 hover:border-flow-600 hover:bg-flow-900 cursor-pointer"
                onClick={() => setCategoryFilter(cat)}
              >
                <div className="flex items-center justify-between">
                  <div className={cn('flex h-9 w-9 items-center justify-center rounded-[6px] border', colorClass)}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <span className={cn('font-mono text-[11px] font-semibold rounded-full px-2 py-0.5 border', colorClass)}>
                    {count} skill{count !== 1 ? 's' : ''}
                  </span>
                </div>
                <div>
                  <p className="font-mono text-sm font-semibold text-foreground group-hover:text-flow-100">
                    {cat}
                  </p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {previews.map(s => (
                    <span
                      key={s.id}
                      className="truncate max-w-[150px] rounded-[4px] border border-flow-800 bg-flow-900 px-2 py-0.5 font-mono text-[10px] text-flow-400"
                    >
                      {s.name}
                    </span>
                  ))}
                  {count > 3 && (
                    <span className="rounded-[4px] border border-flow-800 bg-flow-900 px-2 py-0.5 font-mono text-[10px] text-flow-500">
                      +{count - 3} more
                    </span>
                  )}
                </div>
                <div className="mt-auto flex items-center justify-between gap-2 pt-1 border-t border-flow-800/60">
                  <span className="font-mono text-[10px] text-flow-600 group-hover:text-flow-400 transition-colors">
                    Browse all →
                  </span>
                  {firstSkill && (
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); trainSkill(firstSkill) }}
                      className="flex items-center gap-1 rounded-[4px] border border-flow-violet/30 bg-flow-violet/10 px-2 py-0.5 font-mono text-[10px] text-flow-violet hover:bg-flow-violet/20 hover:border-flow-violet/50 transition-colors"
                    >
                      <BrainCircuit className="h-3 w-3" />
                      Train
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Flat skill grid (when category selected or search active) */}
      {!loading && !showOverview && (
        <>
          {visible.length === 0 ? (
            <div className="rounded-[6px] border border-flow-800 p-10 text-center text-sm text-muted-foreground">
              No skills match.
              {categoryFilter !== 'all' && (
                <button
                  onClick={() => setCategoryFilter('all')}
                  className="ml-2 text-flow-violet underline-offset-4 hover:underline"
                >
                  Clear category
                </button>
              )}
            </div>
          ) : (
            <>
              {categoryFilter !== 'all' && (
                <button
                  onClick={() => setCategoryFilter('all')}
                  className="flex items-center gap-1.5 font-mono text-[11px] text-flow-500 hover:text-flow-200 transition-colors"
                >
                  ← All categories
                </button>
              )}
              <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                {visible.map(skill => (
                  <SkillHubCard key={skill.id} skill={skill} onOpen={openSkill} onTry={tryRun} onTrain={trainSkill} />
                ))}
              </section>
            </>
          )}
        </>
      )}

      {/* Empty overview state */}
      {!loading && showOverview && sortedCategories.length === 0 && (
        <div className="rounded-[8px] border border-dashed border-flow-700 bg-flow-950 p-10 text-center">
          <Store className="mx-auto mb-3 h-8 w-8 text-flow-violet/70" />
          <p className="text-sm font-medium text-foreground">Your hub is empty</p>
          <p className="mx-auto mt-1 max-w-md text-[12px] text-muted-foreground">
            Import a vetted collection (TDD, scientific, academic, product-eng) in one click, or create your own.
          </p>
          <div className="mt-4 flex items-center justify-center gap-3">
            <Link
              href="/skills/marketplace"
              className="inline-flex h-9 items-center gap-1.5 rounded-md bg-flow-violet px-4 font-mono text-xs text-white hover:bg-flow-violet/90"
            >
              <Store className="h-3.5 w-3.5" /> Browse collections
            </Link>
            <Button size="sm" variant="outline" onClick={() => setCreateOpen(true)} className="h-9 gap-1.5 text-xs">
              <Plus className="h-3.5 w-3.5" /> New skill
            </Button>
          </div>
        </div>
      )}

      <SkillDetailSheet
        skill={selected}
        initialTab={initialTab}
        workspaceId={workspaceId ?? undefined}
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
