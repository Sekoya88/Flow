"use client";

import { useStore, type NodeStatus } from "@/lib/store";

const NODES = [
  { id: "planner", label: "Planner", cx: 80, cy: 60 },
  { id: "worker", label: "Worker", cx: 200, cy: 60 },
  { id: "synthesizer", label: "Synthesizer", cx: 320, cy: 60 },
] as const;

const ARCS = [
  {
    id: "plan-work",
    from: { cx: 80, cy: 60 },
    to: { cx: 200, cy: 60 },
    d: "M 95 60 C 130 30, 165 30, 185 60",
  },
  {
    id: "work-synth",
    from: { cx: 200, cy: 60 },
    to: { cx: 320, cy: 60 },
    d: "M 215 60 C 250 30, 285 30, 305 60",
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
      viewBox="0 0 400 120"
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
      </defs>

      {/* Arcs */}
      {ARCS.map((arc) => {
        const fromNode = NODES.find((n) => n.cx === arc.from.cx);
        const toNode = NODES.find((n) => n.cx === arc.to.cx);
        const fromStatus = fromNode ? (nodes[fromNode.id]?.status ?? "idle") : "idle";
        const toStatus = toNode ? (nodes[toNode.id]?.status ?? "idle") : "idle";
        const isActive = fromStatus === "streaming" || fromStatus === "thinking" || toStatus === "thinking";
        const arcColor = isActive
          ? "var(--color-flow-streaming)"
          : fromStatus === "done"
            ? "var(--color-flow-done)"
            : "var(--color-border)";

        return (
          <g key={arc.id}>
            <path
              d={arc.d}
              fill="none"
              stroke={arcColor}
              strokeWidth={isActive ? 2 : 1.5}
              strokeOpacity={isActive ? 0.9 : 0.4}
              markerEnd="url(#arrowhead)"
              style={{ transition: "stroke 0.4s ease, stroke-opacity 0.4s ease" }}
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
              r="18"
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
              cx={node.cx + 12}
              cy={node.cy - 12}
              r="5"
              fill={color}
              style={{ transition: "fill 0.3s ease" }}
            />

            {/* Label */}
            <text
              x={node.cx}
              y={node.cy + 36}
              textAnchor="middle"
              fontSize="10"
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
              fontSize="11"
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
