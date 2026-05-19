import { useEffect, useRef } from 'react'

type AgentEvent = { type: string; [k: string]: unknown }

const ICONS: Record<string, string> = {
  skills_matched:       '✦',
  metacog_evaluated:    '🧠',
  skill_arm_updated:    '📈',
  connection_established: '⚡',
}

const COLORS: Record<string, string> = {
  skills_matched:       '#818cf8',
  metacog_evaluated:    '#a78bfa',
  skill_arm_updated:    '#34d399',
  connection_established: '#22c55e',
}

function describeEvent(e: AgentEvent): string {
  switch (e.type) {
    case 'skills_matched': {
      const s = (e.skills as { name: string }[] | undefined) ?? []
      return `Skills: ${s.map(x => x.name).join(', ') || '—'}`
    }
    case 'metacog_evaluated': {
      const grade = e.grade as number ?? 0
      const bar = '█'.repeat(grade) + '░'.repeat(5 - grade)
      return `Reflection ${bar} ${grade}/5  +${e.mutations_proposed ?? 0} mutations`
    }
    case 'skill_arm_updated': {
      const r = ((e.reward as number) ?? 0).toFixed(2)
      return `Bandit reward ${r} → ${String(e.skill_id).slice(0, 8)}…`
    }
    case 'connection_established':
      return 'Connected'
    default:
      return e.type
  }
}

type Props = { events: AgentEvent[] }

export default function EventFeed({ events }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  if (events.length === 0) {
    return (
      <div style={{ color: '#374151', fontSize: 11, paddingTop: 8 }}>
        Waiting for events…
      </div>
    )
  }

  return (
    <div style={{
      height: 160,
      overflowY: 'auto',
      display: 'flex',
      flexDirection: 'column',
      gap: 3,
    }}>
      {events.map((e, i) => (
        <div
          key={i}
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: 6,
            padding: '3px 6px',
            borderRadius: 5,
            background: i === 0 ? 'rgba(99,102,241,0.08)' : 'transparent',
            transition: 'background 0.3s',
          }}
        >
          <span style={{ fontSize: 11, flexShrink: 0, color: COLORS[e.type] ?? '#6b7280' }}>
            {ICONS[e.type] ?? '·'}
          </span>
          <span style={{
            fontSize: 11,
            color: i === 0 ? '#e5e7eb' : '#9ca3af',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}>
            {describeEvent(e)}
          </span>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
