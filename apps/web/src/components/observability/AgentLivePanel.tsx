'use client'
import { Activity, Bot, CheckCircle2, Circle, Loader2, Wifi, WifiOff } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { useAgentStream } from '@/lib/useAgentStream'
import { SubagentCard } from './SubagentCard'
import { LiveTodoList } from './LiveTodoList'

interface AgentLivePanelProps {
  agentId: string | null
}

const STATE_LABELS: Record<string, string> = {
  idle: 'Idle',
  running: 'Running',
  thinking: 'Thinking',
  complete: 'Complete',
}

const STATE_COLORS: Record<string, string> = {
  idle: 'border-flow-800 text-muted-foreground',
  running: 'border-flow-violet/40 text-flow-violet',
  thinking: 'border-amber-500/40 text-amber-400',
  complete: 'border-emerald-500/40 text-emerald-400',
}

export function AgentLivePanel({ agentId }: AgentLivePanelProps) {
  const { events, subagents, todos, agentState, connected } = useAgentStream(agentId)

  const recentSubagents = subagents.slice(-5).reverse()

  return (
    <div className="space-y-4">
      {/* Status bar */}
      <div className="flow-card flex items-center gap-3 rounded-[6px] border border-flow-800 px-4 py-2.5">
        <span
          className={cn(
            'flex items-center gap-1.5',
            connected ? 'text-emerald-400' : 'text-muted-foreground/50',
          )}
        >
          {connected
            ? <Wifi className="h-3.5 w-3.5" />
            : <WifiOff className="h-3.5 w-3.5" />
          }
          <span className="font-mono text-[10px] uppercase tracking-wider">
            {connected ? 'Live' : 'Disconnected'}
          </span>
        </span>
        <Badge
          variant="outline"
          className={cn('text-[10px]', STATE_COLORS[agentState] ?? STATE_COLORS.idle)}
        >
          {agentState === 'running' && (
            <Loader2 className="mr-1 h-2.5 w-2.5 animate-spin" />
          )}
          {STATE_LABELS[agentState] ?? agentState}
        </Badge>
        <span className="ml-auto font-mono text-[10px] text-muted-foreground/50">
          {events.length} events
        </span>
      </div>

      {/* Todo list */}
      {todos.length > 0 && (
        <div className="flow-card rounded-[6px] border border-flow-800 p-4">
          <div className="mb-3 flex items-center gap-2">
            <CheckCircle2 className="h-3.5 w-3.5 text-muted-foreground/60" />
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">
              Plan
            </span>
          </div>
          <LiveTodoList todos={todos} />
        </div>
      )}

      {/* Subagent calls */}
      {recentSubagents.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Bot className="h-3.5 w-3.5 text-muted-foreground/60" />
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">
              Sub-agents
            </span>
          </div>
          {recentSubagents.map(call => (
            <SubagentCard key={call.id} call={call} />
          ))}
        </div>
      )}

      {/* Event feed */}
      {events.length > 0 && (
        <div className="flow-card rounded-[6px] border border-flow-800 p-4">
          <div className="mb-3 flex items-center gap-2">
            <Activity className="h-3.5 w-3.5 text-muted-foreground/60" />
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">
              Events
            </span>
          </div>
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {events.slice(0, 30).map((evt, i) => (
              <div key={i} className="flex items-center gap-2">
                <Circle className="h-1.5 w-1.5 shrink-0 fill-current text-flow-violet/60" />
                <span className="font-mono text-[11px] text-muted-foreground/60 truncate">
                  {evt.type}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!connected && events.length === 0 && (
        <div className="flow-card rounded-[6px] border border-flow-800 p-8 text-center text-sm text-muted-foreground">
          Connect to an agent to see live activity.
        </div>
      )}
    </div>
  )
}
