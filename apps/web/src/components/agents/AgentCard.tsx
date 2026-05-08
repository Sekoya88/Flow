"use client";

import { useMemo } from "react";
import {
  Bot,
  Brain,
  Code2,
  Database,
  Globe,
  GraduationCap,
  Newspaper,
  Search,
  Sparkles,
  Workflow,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type AgentRow = {
  id: string;
  name: string;
  template: string;
  config: Record<string, unknown>;
  created_at?: string;
  /* injected by parent from stats endpoint later */
  total_runs?: number;
  avg_confidence?: number;
  last_run_at?: string;
};

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const TEMPLATE_STYLES: Record<
  string,
  { label: string; gradient: string; badge: string; icon: typeof Workflow }
> = {
  "linear-3": {
    label: "Linear",
    gradient: "from-teal-500/20 to-teal-500/5",
    badge: "border-teal-500/30 bg-teal-500/10 text-teal-700 dark:text-teal-300",
    icon: Workflow,
  },
  deer_flow: {
    label: "Deer Flow",
    gradient: "from-teal-500/20 to-teal-500/5",
    badge: "border-teal-500/30 bg-teal-500/10 text-teal-700 dark:text-teal-300",
    icon: Workflow,
  },
  "tool-agent": {
    label: "Tool Agent",
    gradient: "from-amber-500/20 to-amber-500/5",
    badge: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
    icon: Zap,
  },
  "researcher-critic-writer": {
    label: "Research",
    gradient: "from-violet-500/20 to-violet-500/5",
    badge: "border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300",
    icon: GraduationCap,
  },
  "human-in-loop": {
    label: "Human-in-Loop",
    gradient: "from-rose-500/20 to-rose-500/5",
    badge: "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300",
    icon: Bot,
  },
  orchestrator: {
    label: "Orchestrator",
    gradient: "from-blue-500/20 to-blue-500/5",
    badge: "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300",
    icon: Sparkles,
  },
};

const TOOL_ICONS: Record<string, { icon: typeof Search; label: string }> = {
  retrieve: { icon: Database, label: "Knowledge" },
  sandbox: { icon: Code2, label: "Sandbox" },
  long_term_memory: { icon: Brain, label: "Memory" },
  tavily_search: { icon: Globe, label: "Web Search" },
  fetch_webpage: { icon: Globe, label: "Fetch URL" },
  arxiv_search: { icon: Search, label: "ArXiv" },
  hf_papers: { icon: Newspaper, label: "HF Papers" },
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function resolveTools(config: Record<string, unknown>): string[] {
  const tools = config?.tools;
  if (!tools || typeof tools !== "object" || Array.isArray(tools)) return [];
  return Object.entries(tools as Record<string, boolean>)
    .filter(([, v]) => v === true)
    .map(([k]) => k);
}

function relativeTime(iso: string | undefined): string {
  if (!iso) return "Never";
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 60_000) return "Just now";
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`;
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`;
  return `${Math.floor(ms / 86_400_000)}d ago`;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

interface AgentCardProps {
  agent: AgentRow;
  onClick?: () => void;
  className?: string;
}

export function AgentCard({ agent, onClick, className }: AgentCardProps) {
  const tpl =
    TEMPLATE_STYLES[agent.template] ?? TEMPLATE_STYLES["linear-3"];
  const TemplateIcon = tpl.icon;
  const enabledTools = useMemo(() => resolveTools(agent.config), [agent.config]);
  const confidence = agent.avg_confidence;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-2xl",
        "border border-border/60 bg-card/80 backdrop-blur-sm",
        "text-left transition-all duration-300 ease-out",
        "hover:border-border hover:shadow-lg hover:shadow-flow-brand/5",
        "hover:-translate-y-0.5",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        className,
      )}
    >
      {/* Gradient accent strip */}
      <div
        className={cn(
          "absolute inset-x-0 top-0 h-1 bg-gradient-to-r transition-all duration-300",
          tpl.gradient,
          "group-hover:h-1.5",
        )}
        aria-hidden
      />

      {/* Content */}
      <div className="flex flex-1 flex-col gap-4 p-5 pt-6">
        {/* Header: name + template badge */}
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h3 className="line-clamp-2 text-sm font-semibold leading-snug text-foreground group-hover:text-flow-brand transition-colors">
              {agent.name || agent.template}
            </h3>
          </div>
          <Badge
            variant="outline"
            className={cn(
              "shrink-0 gap-1 rounded-lg px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide",
              tpl.badge,
            )}
          >
            <TemplateIcon className="h-3 w-3" aria-hidden />
            {tpl.label}
          </Badge>
        </div>

        {/* Tools row */}
        {enabledTools.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {enabledTools.map((tool) => {
              const ti = TOOL_ICONS[tool];
              if (!ti) return null;
              const Icon = ti.icon;
              return (
                <span
                  key={tool}
                  title={ti.label}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-md",
                    "border border-border/40 bg-muted/30 px-2 py-0.5",
                    "text-[10px] font-medium text-muted-foreground",
                    "transition-colors group-hover:border-border/60",
                  )}
                >
                  <Icon className="h-3 w-3" aria-hidden />
                  {ti.label}
                </span>
              );
            })}
          </div>
        )}

        {/* Stats row */}
        <div className="mt-auto flex items-center gap-4 border-t border-border/30 pt-3 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1 tabular-nums">
            <Workflow className="h-3 w-3" aria-hidden />
            {agent.total_runs ?? 0} runs
          </span>
          {confidence !== undefined && confidence > 0 && (
            <span className="flex items-center gap-1 tabular-nums">
              <Sparkles className="h-3 w-3" aria-hidden />
              {(confidence * 100).toFixed(0)}% conf
            </span>
          )}
          <span className="ml-auto">
            {relativeTime(agent.last_run_at || agent.created_at)}
          </span>
        </div>
      </div>
    </button>
  );
}
