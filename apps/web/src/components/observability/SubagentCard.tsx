'use client'
import { useState } from 'react'
import { Bot, CheckCircle2, ChevronDown, ChevronRight, Clock, Loader2, XCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { SubagentCall } from '@/lib/useAgentStream'

interface SubagentCardProps {
  call: SubagentCall
}

function elapsed(startedAt?: number, completedAt?: number): string | null {
  if (!startedAt) return null
  const end = completedAt ?? Date.now() / 1000
  const ms = Math.round((end - startedAt) * 1000)
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function SubagentCard({ call }: SubagentCardProps) {
  const [expanded, setExpanded] = useState(false)

  const statusIcon = {
    running: <Loader2 className="h-3.5 w-3.5 animate-spin text-flow-violet" />,
    complete: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />,
    error: <XCircle className="h-3.5 w-3.5 text-destructive" />,
  }[call.status]

  const statusColor = {
    running: 'border-flow-violet/40 text-flow-violet',
    complete: 'border-emerald-500/40 text-emerald-400',
    error: 'border-destructive/40 text-destructive',
  }[call.status]

  const time = elapsed(call.startedAt, call.completedAt)

  return (
    <div
      className={cn(
        'flow-card rounded-[6px] border border-flow-800 transition-colors',
        call.status === 'running' && 'border-flow-violet/30',
      )}
    >
      <button
        className="flex w-full items-center gap-2 p-3 text-left"
        onClick={() => setExpanded(v => !v)}
      >
        {expanded
          ? <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground/50" />
          : <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground/50" />
        }
        {statusIcon}
        <Bot className="h-3 w-3 shrink-0 text-muted-foreground/60" />
        <span className="min-w-0 flex-1 truncate font-mono text-xs font-semibold text-foreground">
          {call.subagentType}
        </span>
        <Badge variant="outline" className={cn('shrink-0 text-[10px]', statusColor)}>
          {call.status}
        </Badge>
        {time && (
          <span className="flex shrink-0 items-center gap-1 font-mono text-[10px] text-muted-foreground/60">
            <Clock className="h-2.5 w-2.5" />
            {time}
          </span>
        )}
      </button>

      {expanded && (
        <div className="border-t border-flow-800 px-3 pb-3 pt-2 space-y-2">
          <div>
            <p className="mb-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/50">
              Message
            </p>
            <p className="text-xs text-muted-foreground leading-relaxed">{call.description}</p>
          </div>
          {call.result && (
            <div>
              <p className="mb-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/50">
                Result
              </p>
              <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded-[4px] bg-muted/20 p-2 font-mono text-[11px] text-foreground/80 leading-relaxed">
                {call.result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
