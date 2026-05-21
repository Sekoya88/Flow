'use client'
import { Layers } from 'lucide-react'
import type { SkillCatalogRow } from '@/lib/useSkillsCatalog'
import { SkillHubCard } from './SkillHubCard'

interface CategorySectionProps {
  category: string
  skills: SkillCatalogRow[]
  onOpen: (skill: SkillCatalogRow) => void
  onTry: (skill: SkillCatalogRow) => void
}

export function CategorySection({ category, skills, onOpen, onTry }: CategorySectionProps) {
  return (
    <section className="space-y-3">
      <header className="flex items-center gap-2">
        <Layers className="h-3 w-3 text-muted-foreground/60" />
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground/70">
          {category}
        </span>
        <span className="font-mono text-[10px] text-muted-foreground/40">
          {skills.length}
        </span>
        <div className="h-px flex-1 bg-flow-800/60" />
      </header>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {skills.map(skill => (
          <SkillHubCard key={skill.id} skill={skill} onOpen={onOpen} onTry={onTry} />
        ))}
      </div>
    </section>
  )
}
