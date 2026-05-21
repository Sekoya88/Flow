'use client'
import { CheckCircle2, Circle, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Todo } from '@/lib/useAgentStream'

interface LiveTodoListProps {
  todos: Todo[]
}

export function LiveTodoList({ todos }: LiveTodoListProps) {
  if (todos.length === 0) return null

  return (
    <div className="space-y-1.5">
      {todos.map((todo, i) => (
        <div key={i} className="flex items-start gap-2">
          <span className="mt-0.5 shrink-0">
            {todo.status === 'completed' && (
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
            )}
            {todo.status === 'in_progress' && (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-flow-violet" />
            )}
            {todo.status === 'pending' && (
              <Circle className="h-3.5 w-3.5 text-muted-foreground/40" />
            )}
          </span>
          <span
            className={cn(
              'text-xs leading-relaxed',
              todo.status === 'completed' && 'text-muted-foreground/60 line-through',
              todo.status === 'in_progress' && 'text-foreground',
              todo.status === 'pending' && 'text-muted-foreground/70',
            )}
          >
            {todo.content}
          </span>
        </div>
      ))}
    </div>
  )
}
