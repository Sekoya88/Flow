'use client'
import { useCallback, useEffect, useRef, useState } from 'react'

export interface SubagentCall {
  id: string
  status: 'running' | 'complete' | 'error'
  description: string
  subagentType: string
  result?: string
  startedAt?: number
  completedAt?: number
}

export interface Todo {
  status: 'pending' | 'in_progress' | 'completed'
  content: string
}

export interface AgentEvent {
  type: string
  [key: string]: unknown
}

export type AgentState = 'idle' | 'running' | 'thinking' | 'complete'

interface UseAgentStreamResult {
  events: AgentEvent[]
  subagents: SubagentCall[]
  todos: Todo[]
  agentState: AgentState
  connected: boolean
}

const WS_BASE = 'ws://localhost:18000/api/v1/agents'

export function useAgentStream(agentId: string | null): UseAgentStreamResult {
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [subagentMap, setSubagentMap] = useState<Map<string, SubagentCall>>(new Map())
  const [todos, setTodos] = useState<Todo[]>([])
  const [agentState, setAgentState] = useState<AgentState>('idle')
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback((id: string) => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    const ws = new WebSocket(`${WS_BASE}/${id}/ws-observability`)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      reconnectRef.current = setTimeout(() => { if (wsRef.current === ws) connect(id) }, 3000)
    }
    ws.onerror = () => ws.close()

    ws.onmessage = (evt) => {
      try {
        const data: AgentEvent = JSON.parse(evt.data)
        setEvents(prev => [data, ...prev].slice(0, 200))

        if (data.type === 'subagent_call') {
          const call = data as unknown as {
            id: string; status: string; description: string
            subagent_type: string; result?: string
            started_at?: number; completed_at?: number
          }
          setSubagentMap(prev => {
            const next = new Map(prev)
            next.set(call.id, {
              id: call.id,
              status: call.status as SubagentCall['status'],
              description: call.description,
              subagentType: call.subagent_type,
              result: call.result,
              startedAt: call.started_at,
              completedAt: call.completed_at,
            })
            return next
          })
          setAgentState('running')
        } else if (data.type === 'todo_update') {
          const payload = data as unknown as { todos: Todo[] }
          setTodos(payload.todos ?? [])
          setAgentState('thinking')
        } else if (data.type === 'skills_matched') {
          setAgentState('running')
        } else if (data.type === 'metacog_evaluated') {
          setAgentState('thinking')
        } else if (data.type === 'connection_established') {
          setAgentState('idle')
        }
      } catch {
        // ignore parse errors
      }
    }
  }, [])

  useEffect(() => {
    if (!agentId) {
      wsRef.current?.close()
      wsRef.current = null
      setConnected(false)
      setEvents([])
      setSubagentMap(new Map())
      setTodos([])
      setAgentState('idle')
      return
    }
    connect(agentId)
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [agentId, connect])

  return {
    events,
    subagents: Array.from(subagentMap.values()),
    todos,
    agentState,
    connected,
  }
}
