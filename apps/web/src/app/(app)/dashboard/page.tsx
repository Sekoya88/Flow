"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  AlertCircle,
  BookOpen,
  Bot,
  Brain,
  BrainCircuit,
  CalendarClock,
  CheckCircle2,
  Clock,
  Code2,
  Database,
  ExternalLink,
  Layers,
  MessageSquare,
  ScrollText,
  Sparkles,
  Target,
  TrendingUp,
  XCircle,
  Zap,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { FlowMark } from "@/components/brand/FlowLogo";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { ApiError, apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";

type RecentExecution = {
  id: string;
  agent_name: string;
  status: "completed" | "failed" | "running";
  user_message: string;
  created_at: string;
};

type Summary = {
  counts: Record<string, number>;
  recent_executions: RecentExecution[];
};

type Proposal = { id: string; title: string; body: string; status: string; created_at: string };

type ObsStatus = {
  langsmith_enabled: boolean;
  project: string | null;
  trace_url: string | null;
  log_level: string;
};

type TrainingRunRow = {
  id: string;
  status: string;
  epoch: number;
  baseline_score: number | null;
  best_score: number | null;
  accepted: boolean;
  created_at: string;
  skill_name: string;
  agent_name: string;
};

type Project = {
  id: string;
  name: string;
  goal: string;
  arxiv_categories: string[];
  enabled: boolean;
  last_run_at: string | null;
};

const TILES = [
  { key: "agents",           label: "Agents",           href: "/agents",    color: "var(--color-flow-violet)" },
  { key: "executions",       label: "Runs",             href: "/run",       color: "var(--color-flow-streaming)" },
  { key: "active_skills",    label: "Active Skills",    href: "/skills",    color: "var(--color-flow-done)" },
  { key: "training_runs",    label: "Training Runs",    href: "/logs",      color: "#f59e0b" },
  { key: "episodic_memories",label: "Memories",         href: "/memory",    color: "var(--color-flow-thinking)" },
  { key: "active_schedules", label: "Schedules",        href: "/schedules", color: "#6366f1" },
] as const;

const QUICK_LINKS = [
  { href: "/skills",    label: "Skills",    icon: Sparkles },
  { href: "/evals",     label: "Evals",     icon: Target },
  { href: "/logs",      label: "Logs",      icon: Activity },
  { href: "/projects",  label: "Research",  icon: BookOpen },
  { href: "/graph",     label: "Graph",     icon: Layers },
  { href: "/agents",    label: "Agents",    icon: Bot },
  { href: "/memory",    label: "Memory",    icon: Brain },
  { href: "/knowledge", label: "Knowledge", icon: Database },
] as const;

/** Mirrors `services/api/flow/infrastructure/db/schema.sql` — documentation only */
const POSTGRES_MODEL: { table: string; columns: string[] }[] = [
  { table: "users",            columns: ["id", "email", "password_hash", "created_at"] },
  { table: "workspaces",       columns: ["id", "name", "created_at"] },
  { table: "workspace_members",columns: ["workspace_id", "user_id", "role"] },
  { table: "agents",           columns: ["id", "workspace_id", "name", "template", "config", "created_at"] },
  { table: "executions",       columns: ["id", "agent_id", "workspace_id", "status", "error", "user_message", "created_at", "completed_at"] },
  { table: "execution_events", columns: ["id", "execution_id", "kind", "payload", "created_at"] },
  { table: "agent_skills",     columns: ["id", "agent_id", "workspace_id", "name", "content_md", "active", "score", "use_count", "category", "created_at"] },
  { table: "golden_sets",      columns: ["id", "workspace_id", "name", "description", "created_at"] },
  { table: "golden_items",     columns: ["id", "set_id", "input_text", "expected_output", "scoring_criteria"] },
  { table: "skill_training_runs", columns: ["id", "skill_id", "status", "epoch", "baseline_score", "best_score", "accepted", "created_at"] },
  { table: "research_projects",columns: ["id", "workspace_id", "name", "goal", "arxiv_categories", "enabled", "last_run_at"] },
  { table: "episodic_memories",columns: ["id", "workspace_id", "agent_id", "content", "embedding", "created_at"] },
  { table: "agent_schedules",  columns: ["id", "workspace_id", "agent_id", "cron_expr", "enabled", "last_run_at"] },
];

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function DashboardPage() {
  const router = useRouter();
  const routerRef = useRef(router);
  const wsId = useStore((s) => s.workspaces[0]?.id ?? "");

  const [data, setData] = useState<Summary | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [recent, setRecent] = useState<RecentExecution[]>([]);
  const [obsStatus, setObsStatus] = useState<ObsStatus | null>(null);
  const [trainingRuns, setTrainingRuns] = useState<TrainingRunRow[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    if (!getToken()) {
      routerRef.current.replace("/login");
      return;
    }
    setLoading(true);
    setErr(null);
    Promise.all([
      apiFetch<Summary>("/api/v1/dashboard/summary"),
      apiFetch<{ proposals: Proposal[] }>("/api/v1/proposals?status=pending").catch(() => ({ proposals: [] })),
      apiFetch<ObsStatus>("/api/v1/logs/status").catch(() => null),
      apiFetch<{ runs: TrainingRunRow[] }>("/api/v1/skills/training-runs?limit=5").catch(() => ({ runs: [] })),
    ])
      .then(([s, p, obs, tr]) => {
        setData(s);
        setProposals(p.proposals ?? []);
        setRecent(s.recent_executions ?? []);
        setObsStatus(obs);
        setTrainingRuns(tr.runs ?? []);
      })
      .catch((e) => {
        setErr(e instanceof ApiError ? `${e.status}: ${e.body}` : "Could not load dashboard");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { routerRef.current = router; }, [router]);
  useEffect(() => { load(); }, [load]);

  // Load projects separately since we need wsId from store
  useEffect(() => {
    if (!wsId) return;
    apiFetch<{ projects: Project[] }>(`/api/v1/workspaces/${wsId}/projects`)
      .then((r) => setProjects(r.projects ?? []))
      .catch(() => {});
  }, [wsId]);

  if (err) {
    return (
      <div className="w-full space-y-4">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Dashboard error</AlertTitle>
          <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <span>{err}</span>
            <Button type="button" size="sm" variant="outline" onClick={load}>Retry</Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (loading || !data) {
    return (
      <div className="w-full space-y-10">
        <Skeleton className="h-9 w-48" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
          {[1, 2, 3, 4, 5, 6].map((i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
        </div>
        <Skeleton className="h-48 rounded-xl" />
      </div>
    );
  }

  const c = data.counts;

  return (
    <div className="w-full space-y-8 animate-fade-in">
      {/* Hero */}
      <section className="relative overflow-hidden rounded-[6px] border border-flow-800 bg-card p-6 sm:p-8 animate-slide-up">
        <div className="pointer-events-none absolute -right-16 -top-24 h-56 w-56 rounded-full bg-flow-violet/15 blur-3xl dark:bg-flow-violet/25" aria-hidden />
        <div className="relative z-10 flex flex-col gap-2">
          <Badge variant="outline" className="w-fit border-flow-violet/35 bg-flow-violet/10 font-mono text-[10px] uppercase tracking-wider text-flow-violet">
            Workspace Overview
          </Badge>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">System Dashboard</h1>
          <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
            Monitor agent executions, skill training, evaluations, and research digests in real-time.
          </p>
        </div>
      </section>

      {/* LangSmith status banner */}
      {obsStatus && (
        <div className={cn(
          "flex items-center gap-3 rounded-[6px] border px-4 py-3",
          obsStatus.langsmith_enabled
            ? "border-flow-violet/30 bg-flow-violet/5"
            : "border-flow-800 bg-muted/10",
        )}>
          <Bot className={cn("h-4 w-4 shrink-0", obsStatus.langsmith_enabled ? "text-flow-violet" : "text-muted-foreground")} />
          <div className="flex-1 text-sm">
            {obsStatus.langsmith_enabled ? (
              <>LangSmith tracing active — project <span className="font-mono text-flow-violet">{obsStatus.project}</span></>
            ) : (
              <span className="text-muted-foreground">
                LangSmith not configured — add <span className="font-mono text-xs bg-muted px-1 py-0.5 rounded">FLOW_LANGSMITH_API_KEY</span> to <span className="font-mono text-xs">.env</span> to trace all LLM calls
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Badge variant="outline" className="text-[10px] h-5">{obsStatus.log_level}</Badge>
            {obsStatus.trace_url && (
              <a href={obsStatus.trace_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs text-flow-violet hover:underline">
                LangSmith <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>
      )}

      {/* Stat tiles */}
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
        {TILES.map(({ key, label, href, color }, i) => (
          <Link
            key={key}
            href={href}
            className="block transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-flow-violet focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <div
              className="flow-card relative flex min-h-[110px] flex-col overflow-hidden rounded-[6px] p-4 transition-all hover:border-flow-violet/50 hover:shadow-md"
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <div className="pointer-events-none absolute inset-x-0 top-0 h-0.5" style={{ background: color }} aria-hidden />
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
              <p className="mt-auto font-mono text-3xl font-bold tabular-nums text-foreground">{c[key] ?? 0}</p>
            </div>
          </Link>
        ))}
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-4 gap-2 sm:grid-cols-8">
        {QUICK_LINKS.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="flex flex-col items-center gap-1.5 rounded-[6px] border border-flow-800 bg-flow-950 px-2 py-3 text-center transition-colors hover:border-flow-600 hover:bg-flow-900"
          >
            <Icon className="h-4 w-4 text-flow-400" />
            <span className="font-mono text-[10px] text-flow-400">{label}</span>
          </Link>
        ))}
      </div>

      {/* Main grid */}
      <div className="grid gap-4 md:grid-cols-12">
        {/* Quick start */}
        <div className="flow-card flex flex-col items-center justify-center gap-5 rounded-[6px] p-6 md:col-span-4 text-center animate-slide-up [animation-delay:200ms]">
          <FlowMark className="text-flow-violet" size={40} />
          <div className="space-y-1">
            <p className="text-base font-semibold tracking-tight text-foreground">Ready to run</p>
            <p className="text-xs text-muted-foreground">The agent pipeline is standing by.</p>
          </div>
          <div className="flex w-full flex-col gap-2">
            <Link href="/run" className={cn(buttonVariants({ size: "sm" }), "w-full gap-2")}>
              <MessageSquare className="h-3.5 w-3.5" />
              Run Agent
            </Link>
            <Link href="/evals" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "w-full gap-2")}>
              <Target className="h-3.5 w-3.5" />
              Run Evaluation
            </Link>
            <Link href="/knowledge" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "w-full gap-2")}>
              <ScrollText className="h-3.5 w-3.5" />
              Manage Knowledge
            </Link>
          </div>
        </div>

        {/* Recent runs */}
        <div className="flow-card flex flex-col overflow-hidden rounded-[6px] md:col-span-8 animate-slide-up [animation-delay:260ms]">
          <div className="flex items-center gap-2 border-b border-flow-800 bg-muted/20 px-5 py-3">
            <MessageSquare className="h-4 w-4 text-flow-violet" />
            <h3 className="font-semibold text-foreground text-sm">Recent Executions</h3>
            <Link href="/logs" className="ml-auto font-mono text-[10px] text-flow-violet hover:underline">View all</Link>
          </div>
          <div className="flex-1 overflow-auto">
            {recent.length === 0 ? (
              <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">No recent executions.</div>
            ) : (
              <ul className="divide-y divide-border/40">
                {recent.map((r) => (
                  <li key={r.id} className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-muted/10">
                    {r.status === "completed" ? (
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
                    ) : r.status === "failed" ? (
                      <XCircle className="h-3.5 w-3.5 shrink-0 text-destructive" />
                    ) : (
                      <Clock className="h-3.5 w-3.5 shrink-0 animate-pulse text-flow-violet" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-medium text-foreground">
                        {r.user_message || <span className="italic text-muted-foreground">No message</span>}
                      </p>
                      <p className="mt-0.5 flex items-center gap-1.5 font-mono text-[10px] text-muted-foreground">
                        <span className="rounded bg-muted px-1 py-0.5">{r.agent_name}</span>
                        <span>{timeAgo(r.created_at)}</span>
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Recent training runs */}
        <div className="flow-card flex flex-col overflow-hidden rounded-[6px] md:col-span-6 animate-slide-up [animation-delay:300ms]">
          <div className="flex items-center gap-2 border-b border-flow-800 bg-muted/20 px-5 py-3">
            <BrainCircuit className="h-4 w-4 text-flow-violet" />
            <h3 className="font-semibold text-foreground text-sm">Recent Training Runs</h3>
            <Link href="/logs" className="ml-auto font-mono text-[10px] text-flow-violet hover:underline">View all</Link>
          </div>
          <div className="flex-1 overflow-auto">
            {trainingRuns.length === 0 ? (
              <div className="flex h-full items-center justify-center p-6 text-center text-xs text-muted-foreground">
                No training runs yet.{" "}
                <Link href="/skills" className="ml-1 text-flow-violet hover:underline">Improve a skill →</Link>
              </div>
            ) : (
              <ul className="divide-y divide-border/40">
                {trainingRuns.map((run) => {
                  const delta = run.best_score !== null && run.baseline_score !== null
                    ? run.best_score - run.baseline_score
                    : null;
                  return (
                    <li key={run.id} className="flex items-center gap-3 px-5 py-3 hover:bg-muted/10 transition-colors">
                      <TrendingUp className={cn("h-3.5 w-3.5 shrink-0", run.accepted ? "text-emerald-400" : "text-muted-foreground/50")} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium text-foreground">{run.skill_name}</p>
                        <p className="font-mono text-[10px] text-muted-foreground">{run.agent_name} · {timeAgo(run.created_at)}</p>
                      </div>
                      <div className="shrink-0 text-right">
                        {delta !== null && (
                          <span className={cn("font-mono text-[11px] font-semibold", delta > 0 ? "text-emerald-400" : "text-muted-foreground/60")}>
                            {delta > 0 ? "+" : ""}{delta.toFixed(2)}
                          </span>
                        )}
                        <p className={cn("font-mono text-[10px]", run.accepted ? "text-emerald-400" : "text-muted-foreground/50")}>
                          {run.accepted ? "accepted" : run.status}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>

        {/* Research projects */}
        <div className="flow-card flex flex-col overflow-hidden rounded-[6px] md:col-span-6 animate-slide-up [animation-delay:340ms]">
          <div className="flex items-center gap-2 border-b border-flow-800 bg-muted/20 px-5 py-3">
            <BookOpen className="h-4 w-4 text-flow-violet" />
            <h3 className="font-semibold text-foreground text-sm">Research Projects</h3>
            <Link href="/projects" className="ml-auto font-mono text-[10px] text-flow-violet hover:underline">View all</Link>
          </div>
          <div className="flex-1 overflow-auto">
            {projects.length === 0 ? (
              <div className="flex h-full items-center justify-center p-6 text-center text-xs text-muted-foreground">
                No projects yet.{" "}
                <Link href="/projects" className="ml-1 text-flow-violet hover:underline">Create one →</Link>
              </div>
            ) : (
              <ul className="divide-y divide-border/40">
                {projects.slice(0, 5).map((proj) => (
                  <li key={proj.id} className="flex items-start gap-3 px-5 py-3 hover:bg-muted/10 transition-colors">
                    <div className={cn("mt-0.5 h-2 w-2 rounded-full shrink-0", proj.enabled ? "bg-emerald-500" : "bg-muted-foreground/30")} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-medium text-foreground">{proj.name}</p>
                      <p className="font-mono text-[10px] text-muted-foreground">
                        {proj.arxiv_categories.slice(0, 3).join(" · ")}
                        {proj.arxiv_categories.length > 3 && ` +${proj.arxiv_categories.length - 3}`}
                      </p>
                    </div>
                    <span className="shrink-0 font-mono text-[10px] text-muted-foreground/50">
                      {proj.last_run_at ? timeAgo(proj.last_run_at) : "never"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Pending proposals */}
        <div className="flow-card flex flex-col overflow-hidden rounded-[6px] md:col-span-6 animate-slide-up [animation-delay:380ms]">
          <div className="flex items-center gap-2 border-b border-flow-800 bg-muted/20 px-5 py-3">
            <Sparkles className="h-4 w-4 text-flow-violet" />
            <h3 className="font-semibold text-foreground text-sm">Curator Proposals</h3>
            {proposals.length > 0 && (
              <Badge variant="outline" className="ml-auto h-5 rounded-full border-flow-thinking/30 bg-flow-thinking/10 px-2 py-0 font-mono text-[10px] text-flow-violet">
                {proposals.length} pending
              </Badge>
            )}
          </div>
          <div className="p-5">
            {proposals.length === 0 ? (
              <p className="text-xs text-muted-foreground">No pending proposals. Run the agent and submit low-score feedback to generate curator suggestions.</p>
            ) : (
              <ul className="space-y-2">
                {proposals.slice(0, 4).map((p) => (
                  <li key={p.id} className="rounded-[6px] border border-flow-800 bg-flow-950 p-3 text-xs">
                    <p className="line-clamp-1 font-semibold text-foreground">{p.title}</p>
                    <p className="mt-0.5 line-clamp-2 text-muted-foreground">{p.body}</p>
                  </li>
                ))}
                {proposals.length > 4 && (
                  <Link href="/proposals" className="mt-2 block text-center font-mono text-[11px] text-flow-violet hover:underline">
                    +{proposals.length - 4} more proposals
                  </Link>
                )}
              </ul>
            )}
          </div>
        </div>

        {/* Postgres schema reference */}
        <div className="flow-card flex flex-col overflow-hidden rounded-[6px] md:col-span-6 animate-slide-up [animation-delay:420ms]">
          <div className="flex flex-col space-y-1 border-b border-flow-800 bg-muted/20 px-5 py-3">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-flow-violet" />
              <h3 className="font-semibold text-foreground text-sm">Postgres Data Model</h3>
            </div>
            <p className="text-[10px] text-muted-foreground">Core tables — <span className="font-mono">pgvector</span> for retrieval.</p>
          </div>
          <div className="p-4">
            <Accordion multiple={false} className="w-full">
              {POSTGRES_MODEL.map((row) => (
                <AccordionItem key={row.table} value={row.table} className="border-b-border/40">
                  <AccordionTrigger className="py-2.5 font-mono text-[11px] hover:no-underline">
                    <span className="text-foreground">{row.table}</span>
                  </AccordionTrigger>
                  <AccordionContent>
                    <ul className="grid grid-cols-2 gap-1.5 border-l-2 border-flow-violet/25 pl-4 font-mono text-[10px] text-muted-foreground">
                      {row.columns.map((col) => <li key={col} className="truncate" title={col}>{col}</li>)}
                    </ul>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        </div>
      </div>
    </div>
  );
}
