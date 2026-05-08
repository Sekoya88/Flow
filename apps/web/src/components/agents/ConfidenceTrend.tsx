"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";

interface DataPoint {
  confidence: number;
  created_at: string;
  execution_id?: string;
}

interface ConfidenceTrendProps {
  data: DataPoint[];
  className?: string;
  height?: number;
}

import { useRouter } from "next/navigation";

export function ConfidenceTrend({ data, className, height = 48 }: ConfidenceTrendProps) {
  const router = useRouter();
  const path = useMemo(() => {
    if (data.length < 2) return "";
    const width = 200;
    const h = height;
    const pad = 4;
    const pts = [...data].reverse(); // chronological order
    const xStep = (width - pad * 2) / (pts.length - 1);

    const points = pts.map((d, i) => ({
      x: pad + i * xStep,
      y: pad + (1 - d.confidence) * (h - pad * 2),
    }));

    // Smooth curve using catmull-rom → cubic bezier approximation
    let d = `M ${points[0].x} ${points[0].y}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[Math.max(i - 1, 0)];
      const p1 = points[i];
      const p2 = points[i + 1];
      const p3 = points[Math.min(i + 2, points.length - 1)];
      const cp1x = p1.x + (p2.x - p0.x) / 6;
      const cp1y = p1.y + (p2.y - p0.y) / 6;
      const cp2x = p2.x - (p3.x - p1.x) / 6;
      const cp2y = p2.y - (p3.y - p1.y) / 6;
      d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
    }
    return d;
  }, [data, height]);

  const areaPath = useMemo(() => {
    if (!path) return "";
    const width = 200;
    const h = height;
    const pad = 4;
    const pts = [...data].reverse();
    const lastX = pad + (pts.length - 1) * ((width - pad * 2) / (pts.length - 1));
    return `${path} L ${lastX} ${h} L ${pad} ${h} Z`;
  }, [path, data, height]);

  if (data.length < 2) {
    return (
      <div className={cn("flex items-center justify-center text-xs text-muted-foreground", className)}>
        Not enough data for trend
      </div>
    );
  }

  const avg = data.reduce((s, d) => s + d.confidence, 0) / data.length;
  const latest = data[0]?.confidence ?? 0;
  const trend = data.length >= 3
    ? data[0].confidence - data[data.length - 1].confidence
    : 0;

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center gap-3 text-[11px]">
        <span className="font-mono tabular-nums text-foreground font-semibold">
          {(latest * 100).toFixed(0)}%
        </span>
        <span className="text-muted-foreground">latest</span>
        <span className="text-muted-foreground">·</span>
        <span className="font-mono tabular-nums text-muted-foreground">
          {(avg * 100).toFixed(0)}% avg
        </span>
        {trend !== 0 && (
          <>
            <span className="text-muted-foreground">·</span>
            <span className={cn(
              "font-mono tabular-nums",
              trend > 0 ? "text-emerald-500" : "text-rose-500",
            )}>
              {trend > 0 ? "↑" : "↓"} {Math.abs(trend * 100).toFixed(0)}%
            </span>
          </>
        )}
      </div>
      <svg
        viewBox={`0 0 200 ${height}`}
        className="w-full overflow-visible"
        style={{ height }}
        aria-label="Confidence trend sparkline"
      >
        {/* Area fill */}
        <path d={areaPath} fill="url(#confidence-gradient)" opacity="0.15" />
        {/* Line */}
        <path
          d={path}
          fill="none"
          stroke="var(--color-flow-brand)"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Dots at each point */}
        {[...data].reverse().map((d, i) => {
          const pad = 4;
          const xStep = (200 - pad * 2) / (data.length - 1);
          const x = pad + i * xStep;
          const y = pad + (1 - d.confidence) * (height - pad * 2);
          return (
            <circle
              key={i}
              cx={x}
              cy={y}
              r="3"
              fill="var(--color-flow-brand)"
              opacity="0.8"
              className={cn(
                "transition-all duration-200",
                d.execution_id && "cursor-pointer hover:r-4 hover:opacity-100"
              )}
              onClick={() => {
                if (d.execution_id) {
                  router.push(`/run?session=${d.execution_id}`);
                }
              }}
            >
              <title>{`${(d.confidence * 100).toFixed(0)}% — ${new Date(d.created_at).toLocaleDateString()}`}</title>
            </circle>
          );
        })}
        <defs>
          <linearGradient id="confidence-gradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-flow-brand)" stopOpacity="0.6" />
            <stop offset="100%" stopColor="var(--color-flow-brand)" stopOpacity="0" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
}
