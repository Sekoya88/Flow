'use client'

import React, { useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CornerDownRight,
  Loader2,
  Workflow,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export interface SubagentInvocation {
  key: string  // stable id
  agentName: string
  message: string
  status: 'running' | 'success' | 'error'
  answer?: string | null
  durationMs?: number | null
}

interface SubagentCardProps {
  invocation: SubagentInvocation
}

export function SubagentCard({ invocation }: SubagentCardProps) {
  const [open, setOpen] = useState(false)
  const isRunning = invocation.status === 'running'
  const isError = invocation.status === 'error'
  const isDone = invocation.status === 'success'

  return (
    <div
      className={cn(
        'flow-card group rounded-[6px] border p-3 transition-all duration-200 animate-slide-up',
        isError
          ? 'border-destructive/30 hover:border-destructive/50'
          : isRunning
            ? 'border-flow-streaming/40 shadow-flow-streaming/10'
            : 'border-flow-amber/30 hover:border-flow-amber/50',
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 text-left"
        aria-expanded={open}
      >
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        )}
        <div
          className={cn(
            'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border',
            isError
              ? 'border-destructive/40 bg-destructive/15 text-destructive'
              : isRunning
                ? 'border-flow-streaming/40 bg-flow-streaming/15 text-flow-amber'
                : 'border-flow-amber/40 bg-flow-amber/15 text-flow-amber',
          )}
        >
          {isRunning ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : isError ? (
            <AlertCircle className="h-3.5 w-3.5" />
          ) : (
            <Workflow className="h-3.5 w-3.5" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground/70">
              Subagent
            </span>
            <span className="truncate text-sm font-medium text-foreground">
              → {invocation.agentName}
            </span>
          </div>
          <p className="mt-0.5 truncate text-[11px] text-muted-foreground/80">
            {invocation.message}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {invocation.durationMs != null && (
            <span className="font-mono text-[10px] text-muted-foreground/60">
              {(invocation.durationMs / 1000).toFixed(1)}s
            </span>
          )}
          {isDone && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500/80" />}
        </div>
      </button>

      {open && (
        <div className="mt-3 space-y-2 border-t border-flow-800 pt-3 animate-fade-in">
          <div className="rounded-lg bg-muted/30 px-3 py-2">
            <p className="mb-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60">
              Delegated message
            </p>
            <p className="text-[11px] text-foreground/80 leading-relaxed whitespace-pre-wrap">
              {invocation.message}
            </p>
          </div>
          {invocation.answer ? (
            <div
              className={cn(
                'rounded-lg border px-3 py-2',
                isError
                  ? 'border-destructive/30 bg-destructive/[0.05]'
                  : 'border-flow-amber/25 bg-flow-amber/[0.04]',
              )}
            >
              <p className="mb-1 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-flow-amber/80">
                <CornerDownRight className="h-2.5 w-2.5" />
                Subagent response
              </p>
              <p className="text-[12px] leading-relaxed text-foreground/90 whitespace-pre-wrap">
                {invocation.answer}
              </p>
            </div>
          ) : isRunning ? (
            <p className="px-1 text-[11px] italic text-muted-foreground/70">
              Subagent thinking…
            </p>
          ) : null}
        </div>
      )}
    </div>
  )
}
