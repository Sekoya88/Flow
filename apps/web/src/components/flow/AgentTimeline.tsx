import { FlowMark } from "@/components/brand/FlowLogo";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface ExecRow {
  id: string;
  agent_id: string;
  agent_name: string;
  status: "running" | "completed" | "failed";
  user_message: string;
  created_at: string;
  completed_at: string | null;
}

const STATUS_CONFIG: Record<
  ExecRow["status"],
  { label: string; dot: string; badge: string }
> = {
  running: {
    label: "Running",
    dot: "bg-flow-streaming animate-pulse",
    badge: "border-flow-streaming/30 bg-flow-streaming/10 text-foreground",
  },
  completed: {
    label: "Done",
    dot: "bg-flow-done",
    badge: "border-flow-done/30 bg-flow-done/10 text-foreground",
  },
  failed: {
    label: "Failed",
    dot: "bg-flow-error",
    badge: "border-flow-error/30 bg-flow-error/10 text-foreground",
  },
};

function elapsed(created: string, completed: string | null): string {
  const start = new Date(created).getTime();
  const end = completed ? new Date(completed).getTime() : Date.now();
  const ms = end - start;
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`;
}

interface AgentTimelineProps {
  executions: ExecRow[];
  activeId?: string | null;
  className?: string;
}

export function AgentTimeline({ executions, activeId, className }: AgentTimelineProps) {
  if (executions.length === 0) {
    return (
      <p className={cn("text-muted-foreground text-sm", className)}>
        No runs yet. Send a message to start.
      </p>
    );
  }

  return (
    <ol className={cn("relative flex flex-col gap-0", className)} aria-label="Run history">
      {executions.map((exec, i) => {
        const cfg = STATUS_CONFIG[exec.status] ?? STATUS_CONFIG.completed;
        const isLast = i === executions.length - 1;
        const isActive = exec.id === activeId;

        return (
          <li key={exec.id} id={`exec-${exec.id}`} className="relative flex gap-3 scroll-mt-4">
            {/* Vertical connector line */}
            {!isLast && (
              <span
                className="absolute left-[17px] top-[36px] w-px bg-border/50"
                style={{ height: "calc(100% - 4px)" }}
                aria-hidden
              />
            )}

            {/* Avatar */}
            <div
              className={cn(
                "relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border bg-card",
                isActive && "border-flow-streaming/50 shadow-[0_0_8px_1px_color-mix(in_oklch,var(--color-flow-streaming)_30%,transparent)]",
              )}
            >
              <FlowMark
                size={18}
                className={cn(
                  "opacity-70 transition-opacity",
                  isActive && "opacity-100 text-flow-streaming",
                )}
              />
            </div>

            {/* Content */}
            <div className="flex min-w-0 flex-1 flex-col gap-1 pb-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium leading-none text-foreground">
                  {exec.agent_name}
                </span>
                <Badge
                  variant="outline"
                  className={cn("h-5 rounded-full px-2 py-0 text-[10px] font-medium", cfg.badge)}
                >
                  <span className={cn("mr-1 inline-block h-1.5 w-1.5 rounded-full", cfg.dot)} aria-hidden />
                  {cfg.label}
                </Badge>
                <span className="ml-auto text-[10px] tabular-nums text-muted-foreground/70">
                  {elapsed(exec.created_at, exec.completed_at)}
                </span>
              </div>
              {exec.user_message ? (
                <p className="line-clamp-2 text-xs text-muted-foreground">{exec.user_message}</p>
              ) : null}
              <time
                dateTime={exec.created_at}
                className="text-[10px] text-muted-foreground/50"
              >
                {new Date(exec.created_at).toLocaleString(undefined, {
                  dateStyle: "short",
                  timeStyle: "short",
                })}
              </time>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
