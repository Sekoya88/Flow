'use client'

import React from 'react'
import { Crosshair, Globe2, Search } from 'lucide-react'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface GraphControlsProps {
  depth: number  // 0 = unlimited, else N hops
  setDepth: (d: number) => void
  localMode: boolean
  setLocalMode: (b: boolean) => void
  hasFocus: boolean
  onOpenSearch: () => void
  className?: string
}

export function GraphControls({
  depth,
  setDepth,
  localMode,
  setLocalMode,
  hasFocus,
  onOpenSearch,
  className,
}: GraphControlsProps) {
  return (
    <div
      className={cn(
        'surface-glass-heavy w-64 rounded-2xl border border-flow-brand/20 p-4 space-y-4 shadow-xl shadow-flow-brand/10 animate-fade-in',
        className,
      )}
    >
      <div className="flex items-center gap-2">
        <Crosshair className="h-3.5 w-3.5 text-flow-brand" />
        <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-flow-brand/80">
          Graph controls
        </span>
      </div>

      {/* Depth */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label className="text-xs text-muted-foreground">Depth</Label>
          <span
            className={cn(
              'rounded border px-1.5 py-0.5 font-mono text-[10px]',
              depth === 0
                ? 'border-border/40 bg-muted/40 text-muted-foreground'
                : 'border-flow-brand/30 bg-flow-brand/10 text-flow-brand',
            )}
          >
            {depth === 0 ? '∞' : `${depth} hop${depth === 1 ? '' : 's'}`}
          </span>
        </div>
        <Slider
          value={[depth]}
          min={0}
          max={5}
          step={1}
          onValueChange={(v) => {
            const next = Array.isArray(v) ? v[0] : v
            setDepth(typeof next === 'number' ? next : 0)
          }}
          disabled={!hasFocus && depth !== 0}
          className={cn(!hasFocus && depth !== 0 && 'opacity-50')}
        />
        {!hasFocus ? (
          <p className="text-[10px] font-mono text-muted-foreground/60">
            Select a node to enable hop filtering
          </p>
        ) : null}
      </div>

      {/* Local / Global toggle */}
      <div className="flex items-center justify-between gap-3 rounded-lg border border-border/40 bg-card/40 px-3 py-2">
        <div className="flex items-center gap-2">
          <Globe2
            className={cn(
              'h-3.5 w-3.5',
              localMode ? 'text-muted-foreground/40' : 'text-flow-brand',
            )}
          />
          <Label className="text-xs">{localMode ? 'Local graph' : 'Global graph'}</Label>
        </div>
        <Switch
          checked={localMode}
          onCheckedChange={setLocalMode}
          disabled={!hasFocus}
          aria-label="Toggle local vs global graph"
        />
      </div>

      {/* Search trigger */}
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={onOpenSearch}
        className="w-full justify-between gap-2 rounded-lg border-border/50 bg-card/40 text-xs hover:border-flow-brand/40 hover:bg-flow-brand/[0.04]"
      >
        <span className="flex items-center gap-2">
          <Search className="h-3.5 w-3.5" />
          Search nodes…
        </span>
        <span className="rounded border border-border/40 bg-muted/40 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
          ⌘G
        </span>
      </Button>
    </div>
  )
}
