'use client'

import React from 'react'
import { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

type Tone = 'brand' | 'amber' | 'muted' | 'emerald'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: string
  action?: React.ReactNode
  tone?: Tone
  className?: string
}

const TONE_STYLES: Record<Tone, { halo: string; ring: string; iconColor: string; border: string }> = {
  brand: {
    halo: 'bg-flow-brand/10',
    ring: 'ring-flow-brand/15',
    iconColor: 'text-flow-brand',
    border: 'border-flow-brand/20',
  },
  amber: {
    halo: 'bg-amber-500/10',
    ring: 'ring-amber-500/15',
    iconColor: 'text-amber-400',
    border: 'border-amber-500/20',
  },
  emerald: {
    halo: 'bg-emerald-500/10',
    ring: 'ring-emerald-500/15',
    iconColor: 'text-emerald-400',
    border: 'border-emerald-500/20',
  },
  muted: {
    halo: 'bg-muted/40',
    ring: 'ring-border/20',
    iconColor: 'text-muted-foreground',
    border: 'border-border/40',
  },
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  tone = 'brand',
  className,
}: EmptyStateProps) {
  const t = TONE_STYLES[tone]
  return (
    <div
      className={cn(
        'surface-glass relative flex flex-col items-center justify-center gap-4 rounded-2xl border px-8 py-14 text-center animate-fade-in',
        t.border,
        className,
      )}
    >
      <div
        className={cn(
          'flex h-16 w-16 items-center justify-center rounded-2xl ring-4',
          t.halo,
          t.ring,
        )}
      >
        <Icon className={cn('h-7 w-7', t.iconColor)} />
      </div>
      <div className="space-y-1.5">
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        {description && (
          <p className="max-w-sm text-sm text-muted-foreground leading-relaxed">
            {description}
          </p>
        )}
      </div>
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
