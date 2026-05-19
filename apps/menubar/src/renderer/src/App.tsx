import { useEffect, useCallback, useState, useRef } from 'react'
import SkillGraph from './components/SkillGraph'
import EventFeed from './components/EventFeed'

type AgentEvent = { type: string; [k: string]: unknown }

type SkillNode = {
  id: string
  name: string
  score: number
  active: boolean
}

type AppState = 'idle' | 'thinking' | 'reflecting'

type AgentInfo = {
  id: string
  name?: string
  created_at?: string
}

const api = typeof window !== 'undefined' ? window.flowAPI : undefined
const API_BASE = 'http://localhost:18000/api/v1/local'

const STATE_COLOR = { idle: '#6b7280', thinking: '#3b82f6', reflecting: '#a78bfa' }
const STATE_LABEL = { idle: 'Idle', thinking: 'Thinking…', reflecting: 'Reflecting…' }
const STATE_EMOJI = { idle: '', thinking: '⚡', reflecting: '✦' }

// ── Pill ────────────────────────────────────────────────────────
function Pill({ connected, appState, menubarH }: { connected: boolean; appState: AppState; menubarH: number }) {
  return (
    <div style={{
      position: 'absolute',
      top: 0,
      left: '50%',
      transform: 'translateX(-50%)',
      width: 140,
      height: menubarH || 38,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 7,
      cursor: 'default',
      userSelect: 'none',
    }}>
      <div style={{
        width: 7, height: 7, borderRadius: '50%',
        background: connected ? '#22c55e' : '#6b7280',
        boxShadow: connected ? '0 0 8px #22c55ecc' : 'none',
        transition: 'all 0.3s',
        flexShrink: 0,
      }} />
      <span style={{ fontSize: 13, fontWeight: 700, color: '#f9fafb', letterSpacing: '-0.03em' }}>
        Flow
      </span>
      {appState !== 'idle' && (
        <span style={{ fontSize: 11, color: STATE_COLOR[appState] }}>
          {STATE_EMOJI[appState]}
        </span>
      )}
    </div>
  )
}

// ── Panel ───────────────────────────────────────────────────────
function Panel({
  connected, currentAgentId, appState, skills, events, menubarH
}: {
  connected: boolean
  currentAgentId: string | null
  appState: AppState
  skills: SkillNode[]
  events: AgentEvent[]
  menubarH: number
}) {
  return (
    <div style={{
      width: '100%',
      height: '100%',
      background: 'rgba(10,10,16,0.97)',
      backdropFilter: 'blur(50px) saturate(180%)',
      WebkitBackdropFilter: 'blur(50px) saturate(180%)',
      borderRadius: '0 0 20px 20px',
      border: '1px solid rgba(255,255,255,0.09)',
      borderTop: 'none',
      boxShadow: '0 32px 80px rgba(0,0,0,0.8)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      color: '#fff',
      animation: 'slideDown 0.28s cubic-bezier(0.34,1.4,0.64,1) both',
    }}>

      {/* ── Header ── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '14px 16px 10px',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
      }}>
        <div style={{
          width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
          background: connected ? '#22c55e' : '#374151',
          boxShadow: connected ? '0 0 10px #22c55eaa' : 'none',
          transition: 'all 0.3s',
        }} />
        <div style={{ flex: 1 }}>
          <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: '-0.02em', color: '#f9fafb' }}>
            Flow
          </span>
          {currentAgentId && (
            <span style={{ fontSize: 9, color: '#4b5563', marginLeft: 6, fontFamily: 'monospace' }}>
              {currentAgentId.slice(0, 8)}…
            </span>
          )}
        </div>
        <span style={{
          fontSize: 10, color: STATE_COLOR[appState], fontWeight: 600,
          background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: 20,
          border: `1px solid ${STATE_COLOR[appState]}33`, letterSpacing: '0.02em', transition: 'all 0.3s',
        }}>
          {STATE_LABEL[appState]}
        </span>
        <button
          onClick={() => api?.openWebApp()}
          title="Open Flow web app"
          style={{
            background: 'rgba(99,102,241,0.18)', border: '1px solid rgba(99,102,241,0.4)',
            borderRadius: 8, color: '#a5b4fc', fontSize: 11, padding: '4px 10px',
            cursor: 'pointer', fontWeight: 600, letterSpacing: '-0.01em', transition: 'all 0.15s',
          }}
          onMouseEnter={e => (e.currentTarget.style.background = 'rgba(99,102,241,0.35)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'rgba(99,102,241,0.18)')}
        >
          ↗ Open
        </button>
        <button
          onClick={() => api?.quit()}
          title="Quit Flow (close this app)"
          style={{
            background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 8, color: '#6b7280', fontSize: 13, padding: '2px 7px',
            cursor: 'pointer', lineHeight: 1, transition: 'all 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(239,68,68,0.2)'; e.currentTarget.style.color = '#f87171' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; e.currentTarget.style.color = '#6b7280' }}
        >
          ✕
        </button>
      </div>

      {/* ── No agent connected ── */}
      {!connected && (
        <div style={{ padding: '10px 16px 6px' }}>
          <div style={{
            background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)',
            borderRadius: 8, padding: '8px 10px', fontSize: 11, color: '#9ca3af', lineHeight: 1.5,
          }}>
            No agent connected. Start a Flow agent to see live data.
          </div>
        </div>
      )}

      {/* ── Skill graph ── */}
      <div style={{ padding: '10px 16px 4px' }}>
        <div style={{ fontSize: 9, color: '#4b5563', marginBottom: 6, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
          Skill graph
        </div>
        <SkillGraph skills={skills} />
      </div>

      <div style={{ height: 1, background: 'rgba(255,255,255,0.05)', margin: '4px 16px 0' }} />

      {/* ── Event feed ── */}
      <div style={{ flex: 1, minHeight: 0, padding: '8px 16px 10px' }}>
        <div style={{ fontSize: 9, color: '#4b5563', marginBottom: 6, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
          Live events
        </div>
        <EventFeed events={events} />
      </div>

      {/* ── Footer ── */}
      <div style={{
        display: 'flex', gap: 5, padding: '6px 16px 14px',
        borderTop: '1px solid rgba(255,255,255,0.05)',
      }}>
        {[
          {
            label: 'This Agent',
            path: currentAgentId ? `/agents/${currentAgentId}` : '/agents',
            title: currentAgentId ? 'Open current agent details' : 'View all agents',
            active: !!currentAgentId,
          },
          {
            label: 'Runs',
            path: currentAgentId ? `/agents/${currentAgentId}/executions` : '/executions',
            title: 'View recent execution runs',
            active: false,
          },
          {
            label: 'Memory',
            path: currentAgentId ? `/agents/${currentAgentId}/memory` : '/memory',
            title: "View agent's memory and knowledge",
            active: false,
          },
        ].map(({ label, path, title, active }) => (
          <button
            key={path}
            onClick={() => api?.openWebApp(path)}
            title={title}
            style={{
              flex: 1,
              background: active ? 'rgba(99,102,241,0.12)' : 'rgba(255,255,255,0.04)',
              border: `1px solid ${active ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.07)'}`,
              borderRadius: 8, color: active ? '#a5b4fc' : '#6b7280', fontSize: 10, padding: '6px 4px',
              cursor: 'pointer', fontWeight: 600, letterSpacing: '-0.01em', transition: 'all 0.15s',
              display: 'flex', flexDirection: 'column', alignItems: 'center',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(99,102,241,0.18)'; e.currentTarget.style.color = '#a5b4fc' }}
            onMouseLeave={e => { e.currentTarget.style.background = active ? 'rgba(99,102,241,0.12)' : 'rgba(255,255,255,0.04)'; e.currentTarget.style.color = active ? '#a5b4fc' : '#6b7280' }}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Root ────────────────────────────────────────────────────────
export default function App() {
  const [expanded, setExpanded]         = useState(false)
  const [connected, setConnected]       = useState(false)
  const [currentAgentId, setCurrentAgentId] = useState<string | null>(null)
  const [events, setEvents]             = useState<AgentEvent[]>([])
  const [skills, setSkills]             = useState<SkillNode[]>([])
  const [appState, setAppState]         = useState<AppState>('idle')
  const [menubarH, setMenubarH]         = useState(38)
  const agentPollRef                    = useRef<NodeJS.Timeout | null>(null)

  // Receive exact menubar height from main process
  useEffect(() => {
    if (!api) return
    api.onDisplayInfo(({ menubarH: h }) => setMenubarH(h || 38))
  }, [])

  // Auto-discover and silently connect to agents from the Flow API
  const discoverAgents = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/active-agents`)
      if (!res.ok) return
      const data = await res.json()
      const list: AgentInfo[] = Array.isArray(data) ? data : (data.agents ?? data.items ?? [])
      if (list.length > 0 && !currentAgentId && api) {
        const id = list[0].id
        setCurrentAgentId(id)
        api.wsConnect(id)
      }
    } catch {}
  }, [currentAgentId])

  const handleEvent = useCallback((e: AgentEvent) => {
    setEvents(prev => [e, ...prev].slice(0, 60))

    if (e.type === 'skills_matched') {
      const incoming = (e.skills as { name: string; version: string }[]) ?? []
      setSkills(prev => {
        const map = new Map(prev.map(s => [s.name, s]))
        incoming.forEach(({ name }) => {
          if (!map.has(name)) map.set(name, { id: name, name, score: 0.5, active: true })
          else map.set(name, { ...map.get(name)!, active: true })
        })
        map.forEach((v, k) => {
          if (!incoming.find(i => i.name === k)) map.set(k, { ...v, active: false })
        })
        return Array.from(map.values())
      })
      setAppState('thinking')
    }

    if (e.type === 'metacog_evaluated') {
      setAppState('reflecting')
      setTimeout(() => setAppState('idle'), 3000)
    }

    if (e.type === 'skill_arm_updated') {
      const { skill_id, reward } = e as { skill_id: string; reward: number }
      setSkills(prev => prev.map(s => s.id === skill_id ? { ...s, score: reward } : s))
    }
  }, [])

  useEffect(() => {
    if (!api) return
    api.onStatus(s => setConnected(s.connected))
    api.onEvent(e => handleEvent(e))
    return () => api.removeAllListeners()
  }, [handleEvent])

  // Poll every 5s for new agents
  useEffect(() => {
    discoverAgents()
    agentPollRef.current = setInterval(discoverAgents, 5000)
    return () => { if (agentPollRef.current) clearInterval(agentPollRef.current) }
  }, [discoverAgents])

  const onEnter = () => {
    api?.keepOpen()
    api?.expand()
    setExpanded(true)
  }

  const onLeave = () => {
    api?.collapse()
    setExpanded(false)
  }

  return (
    <div
      style={{ width: '100%', height: '100%', background: 'transparent', position: 'relative' }}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
    >
      <Pill connected={connected} appState={appState} menubarH={menubarH} />

      {expanded && (
        <div style={{
          position: 'absolute',
          top: menubarH,
          left: 0, right: 0, bottom: 0,
        }}>
          <Panel
            connected={connected}
            currentAgentId={currentAgentId}
            appState={appState}
            skills={skills}
            events={events}
            menubarH={menubarH}
          />
        </div>
      )}
    </div>
  )
}
