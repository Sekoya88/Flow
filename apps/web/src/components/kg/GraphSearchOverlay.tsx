'use client'

import React, { useEffect } from 'react'
import { Command } from 'cmdk'
import { CornerDownLeft, Search, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

interface GraphNodeForSearch {
  id: string
  label: string
  node_type: string
  summary?: string | null
}

interface GraphSearchOverlayProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  nodes: GraphNodeForSearch[]
  onSelect: (nodeId: string) => void
}

export function GraphSearchOverlay({
  open,
  onOpenChange,
  nodes,
  onSelect,
}: GraphSearchOverlayProps) {
  // Global Cmd+G / Ctrl+G shortcut handled by parent; this only renders on `open`.
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onOpenChange(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onOpenChange])

  if (!open) return null

  return (
    <div
      role="dialog"
      aria-modal
      aria-label="Search graph nodes"
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh] animate-fade-in"
    >
      <div
        className="absolute inset-0 bg-background/70"
        onClick={() => onOpenChange(false)}
        aria-hidden
      />

      <div
        className="relative w-full max-w-xl overflow-hidden rounded-[6px] border border-flow-violet/20 bg-card/95 shadow-none/10 animate-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        <Command className="text-foreground" shouldFilter>
          <div className="flex items-center gap-3 border-b border-flow-800 px-4 py-3">
            <Search className="h-4 w-4 text-flow-violet" />
            <Command.Input
              autoFocus
              placeholder="Search nodes by label or summary…"
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/50"
            />
            <span className="hidden items-center gap-1 rounded border border-flow-800 bg-muted/40 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:flex">
              ⌘G
            </span>
          </div>

          <Command.List className="max-h-[60vh] overflow-y-auto py-2">
            <Command.Empty className="py-8 text-center text-xs text-muted-foreground">
              No matching nodes.
            </Command.Empty>

            {nodes.map((node) => (
              <Command.Item
                key={node.id}
                value={`${node.label} ${node.summary ?? ''} ${node.node_type}`}
                onSelect={() => {
                  onSelect(node.id)
                  onOpenChange(false)
                }}
                className="group flex cursor-pointer items-center gap-3 px-4 py-2.5 text-sm transition-colors aria-selected:bg-flow-violet/10"
              >
                <div
                  className={cn(
                    'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-flow-800 bg-card/50 text-muted-foreground transition-colors group-aria-selected:border-flow-violet/40 group-aria-selected:bg-flow-violet/15 group-aria-selected:text-flow-violet',
                  )}
                  aria-hidden
                >
                  <Sparkles className="h-3.5 w-3.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-foreground/90 group-aria-selected:text-foreground">
                    {node.label}
                  </p>
                  <p className="flex items-center gap-2 text-[11px] text-muted-foreground/70">
                    <span className="rounded border border-flow-800 bg-muted/30 px-1 py-0 font-mono text-[9px] uppercase tracking-wider">
                      {node.node_type}
                    </span>
                    {node.summary && <span className="truncate">{node.summary}</span>}
                  </p>
                </div>
                <CornerDownLeft
                  className="h-3 w-3 shrink-0 text-flow-violet/0 transition-colors group-aria-selected:text-flow-violet/70"
                  aria-hidden
                />
              </Command.Item>
            ))}
          </Command.List>

          <div className="flex items-center justify-between border-t border-flow-800 bg-muted/20 px-4 py-2">
            <div className="flex items-center gap-3 font-mono text-[10px] text-muted-foreground/70">
              <span>↑ ↓ navigate</span>
              <span>⏎ select</span>
              <span>esc close</span>
            </div>
            <span className="font-mono text-[10px] text-muted-foreground/50">
              {nodes.length} nodes
            </span>
          </div>
        </Command>
      </div>
    </div>
  )
}
