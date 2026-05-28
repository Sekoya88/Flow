'use client'
import { Activity, BrainCircuit, Layers, Play, Workflow } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { SkillCatalogRow } from '@/lib/useSkillsCatalog'

const CATEGORY_COLORS: Record<string, string> = {
  Research:      'border-blue-500/40 text-blue-400',
  Code:          'border-emerald-500/40 text-emerald-400',
  Communication: 'border-violet-500/40 text-violet-400',
  Analysis:      'border-amber-500/40 text-amber-400',
  Memory:        'border-pink-500/40 text-pink-400',
  Planning:      'border-cyan-500/40 text-cyan-400',
  General:       'border-flow-800 text-muted-foreground',
}

interface SkillHubCardProps {
  skill: SkillCatalogRow
  onOpen: (skill: SkillCatalogRow) => void
  onTry: (skill: SkillCatalogRow) => void
  onTrain?: (skill: SkillCatalogRow) => void
}

export function SkillHubCard({ skill, onOpen, onTry, onTrain }: SkillHubCardProps) {
  const shownTriggers = skill.triggers.slice(0, 3)
  const extra = skill.triggers.length - shownTriggers.length

  return (
    <article
      className="flow-card group flex h-full cursor-pointer flex-col gap-3 rounded-[6px] border border-flow-800 p-4 transition-colors hover:border-flow-violet/50"
      onClick={() => onOpen(skill)}
    >
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate font-mono text-sm font-semibold tracking-tight text-foreground">
            {skill.name}
          </h3>
          <div className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <Workflow className="h-3 w-3" />
            <span className="truncate">{skill.agent_name}</span>
          </div>
          {skill.category && skill.category !== 'General' && (
            <div className="mt-1">
              <Badge
                variant="outline"
                className={cn('text-[9px] px-1.5 py-0', CATEGORY_COLORS[skill.category] ?? CATEGORY_COLORS.General)}
              >
                {skill.category}
              </Badge>
            </div>
          )}
        </div>
        <Badge variant="outline" className="shrink-0 font-mono text-[10px]">
          v{skill.version}
        </Badge>
      </header>

      {skill.description && (
        <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
          {skill.description}
        </p>
      )}

      {shownTriggers.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {shownTriggers.map((t, i) => (
            <Badge
              key={`${t}-${i}`}
              variant="outline"
              className="max-w-full truncate border-flow-800 text-[10px] text-muted-foreground"
            >
              {t}
            </Badge>
          ))}
          {extra > 0 && (
            <span className="text-[10px] text-muted-foreground/60">+{extra}</span>
          )}
        </div>
      )}

      <footer className="mt-auto flex items-center justify-between gap-2 pt-1">
        <div className="flex items-center gap-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">
          <span className="flex items-center gap-1">
            <Activity className="h-3 w-3" />
            {skill.score.toFixed(2)}
          </span>
          <span className="flex items-center gap-1">
            <Layers className="h-3 w-3" />
            {skill.use_count} runs
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {onTrain && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="text-flow-violet/70 hover:text-flow-violet hover:bg-flow-violet/10 transition-colors"
              onClick={(e) => {
                e.stopPropagation()
                onTrain(skill)
              }}
            >
              <BrainCircuit className="mr-1 h-3 w-3" />
              Train
            </Button>
          )}
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="border-flow-violet/40 text-flow-violet opacity-80 transition-opacity group-hover:opacity-100"
            onClick={(e) => {
              e.stopPropagation()
              onTry(skill)
            }}
          >
            <Play className="mr-1 h-3 w-3" />
            Try
          </Button>
        </div>
      </footer>
    </article>
  )
}
