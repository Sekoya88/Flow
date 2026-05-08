"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  BookOpen,
  Brain,
  CalendarClock,
  CheckCircle2,
  Clock,
  Database,
  MessageSquare,
  ScrollText,
  Sparkles,
  XCircle,
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
import { FlowMarkAnimated } from "@/components/brand/FlowLogo";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { ApiError, apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";
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

const TILES = [
  { key: "agents", label: "Agents", href: "/agents" },
  { key: "executions", label: "Runs", href: "/run" },
  { key: "episodic_memories", label: "Memories", href: "/memory" },
  { key: "active_schedules", label: "Active schedules", href: "/schedules" },
] as const;

/** Mirrors `services/api/flow/infrastructure/db/schema.sql` — documentation only */
const POSTGRES_MODEL: { table: string; columns: string[] }[] = [
  {
    table: "users",
    columns: ["id", "email", "password_hash", "created_at"],
  },
  {
    table: "workspaces",
    columns: ["id", "name", "created_at"],
  },
  {
    table: "workspace_members",
    columns: ["workspace_id", "user_id", "role"],
  },
  {
    table: "agents",
    columns: ["id", "workspace_id", "name", "template", "config", "created_at"],
  },
  {
    table: "executions",
    columns: [
      "id",
      "agent_id",
      "workspace_id",
      "status",
      "error",
      "user_message",
      "created_at",
      "completed_at",
    ],
  },
  {
    table: "execution_events",
    columns: ["id", "execution_id", "kind", "payload", "created_at"],
  },
  {
    table: "episodic_memories",
    columns: ["id", "workspace_id", "agent_id", "user_id", "execution_id", "content", "embedding", "created_at"],
  },
  {
    table: "reasoning_patterns",
    columns: ["id", "workspace_id", "agent_id", "problem_summary", "solution_steps", "embedding", "score", "use_count", "created_at"],
  },
  {
    table: "agent_schedules",
    columns: ["id", "workspace_id", "agent_id", "user_id", "cron_expr", "prompt_template", "delivery_type", "delivery_target", "enabled", "last_run_at", "created_at"],
  },
];

export default function DashboardPage() {
  const router = useRouter();
  const routerRef = useRef(router);
  const [data, setData] = useState<Summary | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [recent, setRecent] = useState<RecentExecution[]>([]);
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
      apiFetch<{ proposals: Proposal[] }>("/api/v1/proposals?status=pending").catch(() => ({
        proposals: [],
      })),
    ])
      .then(([s, p]) => {
        setData(s);
        setProposals(p.proposals ?? []);
        setRecent(s.recent_executions ?? []);
      })
      .catch((e) => {
        setErr(e instanceof ApiError ? `${e.status}: ${e.body}` : "Could not load dashboard");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    routerRef.current = router;
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  if (err) {
    return (
      <div className="w-full space-y-4">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Dashboard error</AlertTitle>
          <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <span>{err}</span>
            <Button type="button" size="sm" variant="outline" onClick={load}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (loading || !data) {
    return (
      <div className="w-full space-y-10">
        <Skeleton className="h-9 w-48" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-48 rounded-xl" />
      </div>
    );
  }

  const c = data.counts;

  return (
    <div className="w-full space-y-12 animate-fade-in">
      {/* Hero / Header */}
      <section className="relative overflow-hidden rounded-2xl border border-border/60 bg-card/40 p-6 shadow-sm backdrop-blur-md sm:p-8 animate-slide-up">
        <div className="pointer-events-none absolute -right-16 -top-24 h-56 w-56 rounded-full bg-flow-brand/15 blur-3xl dark:bg-flow-brand/25" aria-hidden />
        <div className="relative z-10 flex flex-col gap-2">
          <Badge
            variant="outline"
            className="w-fit border-flow-brand/35 bg-flow-brand/10 font-mono text-[10px] uppercase tracking-wider text-flow-brand"
          >
            Workspace Overview
          </Badge>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">
            System Dashboard
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
            Monitor agent executions, explore the knowledge graph, and review curator proposals in real-time.
          </p>
        </div>
      </section>

      {/* Stat tiles */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {TILES.map(({ key, label, href }, i) => (
          <Link
            key={key}
            href={href}
            className="block transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-flow-brand focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <div
              className={cn(
                "surface-glass relative flex min-h-[120px] flex-col overflow-hidden rounded-2xl p-5 transition-all hover:border-flow-brand/40 hover:shadow-md",
                key === "active_schedules" && c[key] > 0 && "border-flow-thinking/40 bg-flow-thinking/5",
              )}
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <div
                className="pointer-events-none absolute inset-x-0 top-0 h-1"
                style={{
                  background:
                    key === "agents"
                      ? "var(--color-flow-brand)"
                      : key === "executions"
                        ? "var(--color-flow-streaming)"
                        : key === "episodic_memories"
                          ? "var(--color-flow-done)"
                          : "var(--color-flow-thinking)",
                }}
                aria-hidden
              />
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                {label}
              </p>
              <p className="mt-auto font-mono text-4xl font-bold tabular-nums text-foreground">
                {c[key] ?? 0}
              </p>
            </div>
          </Link>
        ))}
      </div>

      {/* Feature Bento */}
      <div className="grid gap-4 md:grid-cols-12">
        {/* Quick start */}
        <div className="surface-glass flex flex-col items-center justify-center gap-6 rounded-2xl p-8 md:col-span-5 text-center animate-slide-up [animation-delay:200ms]">
          <FlowMarkAnimated className="text-flow-brand" size={48} />
          <div className="space-y-2">
            <p className="text-lg font-semibold tracking-tight text-foreground">Ready to run</p>
            <p className="text-sm text-muted-foreground">
              The agent pipeline is standing by.
            </p>
          </div>
          <div className="flex w-full flex-col gap-2">
            <Link href="/run" className={cn(buttonVariants({ size: "default" }), "w-full gap-2")}>
              <MessageSquare className="h-4 w-4" aria-hidden />
              Run Agent
            </Link>
            <Link
              href="/knowledge"
              className={cn(buttonVariants({ variant: "outline", size: "default" }), "w-full gap-2")}
            >
              <ScrollText className="h-4 w-4" aria-hidden />
              Manage Knowledge
            </Link>
          </div>
        </div>

        {/* Recent runs */}
        <div className="surface-glass flex flex-col overflow-hidden rounded-2xl md:col-span-7 animate-slide-up [animation-delay:260ms]">
          <div className="flex items-center gap-2 border-b border-border/60 bg-muted/20 px-6 py-4">
            <MessageSquare className="h-4 w-4 text-flow-streaming" />
            <h3 className="font-semibold text-foreground">Recent Executions</h3>
          </div>
          <div className="flex-1 overflow-auto p-0">
            {recent.length === 0 ? (
              <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
                No recent executions.
              </div>
            ) : (
              <ul className="divide-y divide-border/40">
                {recent.map((r) => (
                  <li key={r.id} className="flex items-center gap-3 px-6 py-3.5 transition-colors hover:bg-muted/10">
                    {r.status === "completed" ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
                    ) : r.status === "failed" ? (
                      <XCircle className="h-4 w-4 shrink-0 text-destructive" />
                    ) : (
                      <Clock className="h-4 w-4 shrink-0 animate-pulse text-flow-streaming" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-foreground">
                        {r.user_message || <span className="text-muted-foreground italic">No message</span>}
                      </p>
                      <p className="mt-0.5 flex items-center gap-2 font-mono text-[10px] text-muted-foreground">
                        <span className="rounded-full bg-muted px-1.5 py-0.5">{r.agent_name}</span>
                        <span>{r.id.split('-')[0]}</span>
                      </p>
                    </div>
                    <time className="shrink-0 font-mono text-[10px] text-muted-foreground">
                      {new Date(r.created_at).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })}
                    </time>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Pending proposals */}
        <div className="surface-glass flex flex-col overflow-hidden rounded-2xl md:col-span-6 animate-slide-up [animation-delay:320ms]">
          <div className="flex items-center gap-2 border-b border-border/60 bg-muted/20 px-6 py-4">
            <Sparkles className="h-4 w-4 text-flow-thinking" aria-hidden />
            <h3 className="font-semibold text-foreground">Curator Proposals</h3>
            {proposals.length > 0 && (
              <Badge
                variant="outline"
                className="ml-auto h-5 rounded-full border-flow-thinking/30 bg-flow-thinking/10 px-2 py-0 font-mono text-[10px] text-flow-thinking"
              >
                {proposals.length} pending
              </Badge>
            )}
          </div>
          <div className="p-6">
            {proposals.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No pending proposals. Run the agent and submit low-score feedback to generate curator
                suggestions.
              </p>
            ) : (
              <ul className="space-y-3">
                {proposals.slice(0, 4).map((p) => (
                  <li
                    key={p.id}
                    className="rounded-xl border border-border/50 bg-background/50 p-3 text-xs leading-snug shadow-sm"
                  >
                    <p className="line-clamp-1 font-semibold text-foreground">{p.title}</p>
                    <p className="mt-1 line-clamp-2 text-muted-foreground">{p.body}</p>
                    <p className="mt-2 font-mono text-[9px] text-muted-foreground/60">{p.id}</p>
                  </li>
                ))}
                {proposals.length > 4 && (
                  <Link
                    href="/proposals"
                    className="mt-3 block text-center font-mono text-[11px] text-flow-brand transition-colors hover:text-flow-brand/80"
                  >
                    +{proposals.length - 4} MORE PROPOSALS
                  </Link>
                )}
              </ul>
            )}
          </div>
        </div>

      <Separator className="bg-border/60" />

        {/* Postgres schema reference */}
        <div className="surface-glass flex flex-col overflow-hidden rounded-2xl md:col-span-6 animate-slide-up [animation-delay:380ms]">
          <div className="flex flex-col space-y-1 border-b border-border/60 bg-muted/20 px-6 py-4">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-flow-brand" aria-hidden />
              <h3 className="font-semibold text-foreground">Postgres Data Model</h3>
            </div>
            <p className="text-xs text-muted-foreground">
              Core tables behind Flow — <span className="font-mono text-[10px] text-foreground/90">pgvector</span> for retrieval.
            </p>
          </div>
          <div className="p-4">
            <Accordion multiple={false} className="w-full">
              {POSTGRES_MODEL.map((row) => (
                <AccordionItem key={row.table} value={row.table} className="border-b-border/40">
                  <AccordionTrigger className="py-3 font-mono text-xs hover:no-underline">
                    <span className="text-foreground">{row.table}</span>
                  </AccordionTrigger>
                  <AccordionContent>
                    <ul className="grid grid-cols-2 gap-2 border-l-2 border-flow-brand/25 pl-4 font-mono text-[10px] text-muted-foreground">
                      {row.columns.map((col) => (
                        <li key={col} className="truncate" title={col}>{col}</li>
                      ))}
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
