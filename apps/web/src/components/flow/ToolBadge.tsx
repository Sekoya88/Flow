import { type ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { NodeStatus } from "@/lib/store";

const STATUS_DOT: Record<NodeStatus, string> = {
  idle: "bg-flow-idle",
  thinking: "bg-flow-thinking",
  streaming: "bg-flow-streaming animate-pulse",
  done: "bg-flow-done",
  error: "bg-flow-error",
};

interface ToolBadgeProps {
  label: string;
  status?: NodeStatus;
  icon?: ReactNode;
  className?: string;
}

export function ToolBadge({ label, status = "idle", icon, className }: ToolBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-flow-800 bg-muted/50 px-2.5 py-1 text-xs font-medium text-foreground/80",
        className,
      )}
    >
      {icon ? <span className="shrink-0 opacity-70">{icon}</span> : null}
      <span className="truncate">{label}</span>
      <span
        className={cn("h-1.5 w-1.5 shrink-0 rounded-full", STATUS_DOT[status])}
        aria-label={status}
      />
    </span>
  );
}
