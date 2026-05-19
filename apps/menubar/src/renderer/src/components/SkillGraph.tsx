import { useEffect, useRef } from 'react'

type SkillNode = {
  id: string
  name: string
  score: number
  active: boolean
}

type Props = { skills: SkillNode[] }

// Fixed positions for up to 8 skills arranged in a flower pattern
const POSITIONS = [
  { x: 0, y: 0 },           // center
  { x: 60, y: 0 },
  { x: -60, y: 0 },
  { x: 0, y: 48 },
  { x: 0, y: -48 },
  { x: 48, y: 38 },
  { x: -48, y: 38 },
  { x: 48, y: -38 },
]

const W = 350
const H = 140
const CX = W / 2
const CY = H / 2

export default function SkillGraph({ skills }: Props) {
  if (skills.length === 0) {
    return (
      <div style={{
        height: H,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#374151',
        fontSize: 11,
      }}>
        No skills active yet
      </div>
    )
  }

  const nodes = skills.slice(0, 8).map((s, i) => ({
    ...s,
    x: CX + (POSITIONS[i]?.x ?? 0),
    y: CY + (POSITIONS[i]?.y ?? 0),
  }))

  return (
    <svg width={W} height={H} style={{ overflow: 'visible' }}>
      {/* edges from center to each satellite */}
      {nodes.slice(1).map((n) => (
        <line
          key={`edge-${n.id}`}
          x1={nodes[0].x} y1={nodes[0].y}
          x2={n.x} y2={n.y}
          stroke="rgba(99,102,241,0.25)"
          strokeWidth={1}
          strokeDasharray={n.active ? 'none' : '3 3'}
        />
      ))}

      {/* nodes */}
      {nodes.map((n) => {
        const r = 18 + n.score * 8  // radius scales with bandit score
        const color = n.active
          ? `rgba(99,102,241,${0.4 + n.score * 0.6})`
          : 'rgba(75,85,99,0.35)'
        const textColor = n.active ? '#c7d2fe' : '#6b7280'
        const label = n.name.length > 10 ? n.name.slice(0, 9) + '…' : n.name

        return (
          <g key={n.id} style={{ transition: 'all 0.3s ease' }}>
            {/* glow ring when active */}
            {n.active && (
              <circle
                cx={n.x} cy={n.y} r={r + 4}
                fill="none"
                stroke="rgba(99,102,241,0.2)"
                strokeWidth={2}
              />
            )}
            <circle
              cx={n.x} cy={n.y} r={r}
              fill={color}
              stroke={n.active ? 'rgba(165,180,252,0.5)' : 'rgba(107,114,128,0.3)'}
              strokeWidth={1}
            />
            <text
              x={n.x} y={n.y + 1}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize={8}
              fontFamily="-apple-system, sans-serif"
              fontWeight={600}
              fill={textColor}
            >
              {label}
            </text>
            {/* score bar at bottom of node */}
            <rect
              x={n.x - r + 2} y={n.y + r - 5}
              width={(r * 2 - 4) * n.score}
              height={3}
              rx={1.5}
              fill="rgba(165,180,252,0.7)"
            />
          </g>
        )
      })}
    </svg>
  )
}
