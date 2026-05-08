"use client";

import { useStore, type NodeStatus } from "@/lib/store";

const NODES = [
  { id: "planner", label: "Planner", cx: 60, cy: 60 },
  { id: "worker", label: "Worker", cx: 170, cy: 60 },
  { id: "synthesizer", label: "Synthesizer", cx: 280, cy: 60 },
  { id: "reflector", label: "Reflector", cx: 390, cy: 60 },
] as const;

const ARCS = [
  {
    id: "plan-work",
    from: { cx: 60, cy: 60 },
    to: { cx: 170, cy: 60 },
    d: "M 78 60 C 110 30, 140 30, 152 60",
  },
  {
    id: "work-synth",
    from: { cx: 170, cy: 60 },
    to: { cx: 280, cy: 60 },
    d: "M 188 60 C 220 30, 250 30, 262 60",
  },
  {
    id: "synth-reflect",
    from: { cx: 280, cy: 60 },
    to: { cx: 390, cy: 60 },
    d: "M 298 60 C 330 30, 360 30, 372 60",
  },
] as const;

const STATUS_COLORS: Record<NodeStatus, string> = {
  idle: "var(--color-flow-idle)",
  thinking: "var(--color-flow-thinking)",
  streaming: "var(--color-flow-streaming)",
  done: "var(--color-flow-done)",
  error: "var(--color-flow-error)",
};

const STATUS_GLOW: Record<NodeStatus, string> = {
  idle: "none",
  thinking: "0 0 12px 2px color-mix(in oklch, var(--color-flow-thinking) 60%, transparent)",
  streaming: "0 0 16px 3px color-mix(in oklch, var(--color-flow-streaming) 60%, transparent)",
  done: "0 0 8px 1px color-mix(in oklch, var(--color-flow-done) 40%, transparent)",
  error: "0 0 10px 2px color-mix(in oklch, var(--color-flow-error) 50%, transparent)",
};

interface FlowGraphProps {
  className?: string;
}

export function FlowGraph({ className }: FlowGraphProps) {
  const nodes = useStore((s) => s.nodes);

  return (
    <svg
      viewBox="0 0 450 120"
      aria-label="Agent execution graph"
      role="img"
      className={className}
      style={{ overflow: "visible" }}
    >
      <defs>
        <marker
          id="arrowhead"
          markerWidth="6"
          markerHeight="6"
          refX="5"
          refY="3"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path d="M 0 0 L 6 3 L 0 6 Z" fill="var(--color-border)" opacity="0.6" />
        </marker>
        {/* Gradient for active arcs */}
        <linearGradient id="arc-active" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="var(--color-flow-thinking)" stopOpacity="0.4" />
          <stop offset="50%" stopColor="var(--color-flow-streaming)" stopOpacity="0.9" />
          <stop offset="100%" stopColor="var(--color-flow-streaming)" stopOpacity="0.4" />
        </linearGradient>
      </defs>

      {/* Arcs */}
      {ARCS.map((arc) => {
        const fromNode = NODES.find((n) => n.cx === arc.from.cx);
        const toNode = NODES.find((n) => n.cx === arc.to.cx);
        const fromStatus = fromNode ? (nodes[fromNode.id]?.status ?? "idle") : "idle";
        const toStatus = toNode ? (nodes[toNode.id]?.status ?? "idle") : "idle";
        const isActive = fromStatus === "streaming" || fromStatus === "thinking" || toStatus === "thinking";
        const isDone = fromStatus === "done";
        const arcColor = isActive
          ? "url(#arc-active)"
          : isDone
            ? "var(--color-flow-done)"
            : "var(--color-border)";

        return (
          <g key={arc.id}>
            <path
              d={arc.d}
              fill="none"
              stroke={arcColor}
              strokeWidth={isActive ? 2.5 : 1.5}
              strokeOpacity={isActive ? 0.9 : isDone ? 0.5 : 0.3}
              markerEnd="url(#arrowhead)"
              style={{ transition: "stroke 0.4s ease, stroke-opacity 0.4s ease, stroke-width 0.3s ease" }}
            />
            {/* Animated dot riding the arc when active */}
            {isActive && (
              <circle r="4" fill="var(--color-flow-streaming)" opacity="0.9">
                <animateMotion dur="1.2s" repeatCount="indefinite" path={arc.d} />
              </circle>
            )}
          </g>
        );
      })}

      {/* Nodes */}
      {NODES.map((node) => {
        const state = nodes[node.id];
        const status: NodeStatus = state?.status ?? "idle";
        const color = STATUS_COLORS[status];
        const isActive = status === "thinking" || status === "streaming";

        return (
          <g key={node.id}>
            {/* Glow ring when active */}
            {isActive && (
              <circle
                cx={node.cx}
                cy={node.cy}
                r="22"
                fill="none"
                stroke={color}
                strokeWidth="1"
                opacity="0.35"
                style={{
                  animation: "ping 1.5s cubic-bezier(0,0,0.2,1) infinite",
                }}
              />
            )}

            {/* Node circle */}
            <circle
              cx={node.cx}
              cy={node.cy}
              r="16"
              fill="var(--color-card)"
              stroke={color}
              strokeWidth={isActive ? 2 : 1.5}
              style={{
                transition: "stroke 0.3s ease",
                filter: isActive ? STATUS_GLOW[status] : "none",
              }}
            />

            {/* Status dot */}
            <circle
              cx={node.cx + 11}
              cy={node.cy - 11}
              r="4"
              fill={color}
              style={{ transition: "fill 0.3s ease" }}
            />

            {/* Label */}
            <text
              x={node.cx}
              y={node.cy + 32}
              textAnchor="middle"
              fontSize="9"
              fill="var(--color-muted-foreground)"
              fontFamily="var(--font-sans)"
              style={{ userSelect: "none" }}
            >
              {node.label}
            </text>

            {/* Node initials */}
            <text
              x={node.cx}
              y={node.cy + 4}
              textAnchor="middle"
              fontSize="10"
              fontWeight="600"
              fill={isActive ? color : "var(--color-foreground)"}
              fontFamily="var(--font-sans)"
              style={{
                userSelect: "none",
                transition: "fill 0.3s ease",
              }}
            >
              {node.label.slice(0, 1)}
            </text>
          </g>
        );
      })}

      <style>{`
        @keyframes ping {
          0% { transform-origin: center; transform: scale(1); opacity: 0.35; }
          100% { transform-origin: center; transform: scale(1.6); opacity: 0; }
        }
      `}</style>
    </svg>
  );
}
