"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, BookOpen, MessageSquare, ScrollText, Sparkles } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { FlowMarkAnimated } from "@/components/brand/FlowLogo";
import { ApiError, apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Summary = { counts: Record<string, number> };
type Proposal = { id: string; title: string; body: string; status: string; created_at: string };

const TILES = [
  { key: "agents", label: "Agents", href: "/settings" },
  { key: "executions", label: "Runs", href: "/run" },
  { key: "knowledge", label: "Sources", href: "/knowledge" },
  { key: "pending_proposals", label: "Proposals", href: "/proposals" },
] as const;

export default function DashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<Summary | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    setLoading(true);
    setErr(null);
    Promise.all([
      apiFetch<Summary>("/api/v1/dashboard/summary"),
      apiFetch<{ proposals: Proposal[] }>("/api/v1/proposals?status=pending").catch(() => ({ proposals: [] })),
    ])
      .then(([s, p]) => {
        setData(s);
        setProposals(p.proposals ?? []);
      })
      .catch((e) => {
        setErr(e instanceof ApiError ? `${e.status}: ${e.body}` : "Could not load dashboard");
      })
      .finally(() => setLoading(false));
  }, [router]);

  useEffect(() => { load(); }, [load]);

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
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1,2,3,4].map((i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
        </div>
        <Skeleton className="h-48 rounded-xl" />
      </div>
    );
  }

  const c = data.counts;

  return (
    <div className="w-full space-y-10 animate-fade-in">
      {/* Hero */}
      <header className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <h1 className="font-heading text-3xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Workspace at a glance. All agents, runs, and knowledge in one view.
          </p>
        </div>
        <Link
          href="/run"
          className={cn(
            buttonVariants({ size: "lg" }),
            "shrink-0 gap-2 shadow-sm",
          )}
        >
          <MessageSquare className="h-4 w-4" aria-hidden />
          Run agent
        </Link>
      </header>

      {/* Stat tiles */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {TILES.map(({ key, label, href }, i) => (
          <Link
            key={key}
            href={href}
            className="block transition-transform hover:-translate-y-0.5 focus-visible:outline-none"
          >
            <Card
              className={cn(
                "relative overflow-hidden shadow-sm transition-shadow hover:shadow-md",
                key === "pending_proposals" && c[key] > 0 && "border-flow-thinking/40",
              )}
              style={{ animationDelay: `${i * 60}ms` }}
            >
              {/* Subtle gradient accent */}
              <div
                className="pointer-events-none absolute inset-x-0 top-0 h-1 rounded-t-lg"
                style={{
                  background:
                    key === "agents"
                      ? "var(--color-flow-brand)"
                      : key === "executions"
                        ? "var(--color-flow-streaming)"
                        : key === "knowledge"
                          ? "var(--color-flow-done)"
                          : "var(--color-flow-thinking)",
                }}
                aria-hidden
              />
              <CardHeader className="pb-2 pt-5">
                <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-4xl font-semibold tabular-nums">{c[key] ?? 0}</p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
        {/* Animated brand + quick actions */}
        <Card className="flex flex-col items-center gap-6 py-10 shadow-sm">
          <FlowMarkAnimated className="text-flow-brand opacity-85" />
          <div className="space-y-1 text-center">
            <p className="text-lg font-semibold tracking-tight">Ready to run</p>
            <p className="text-muted-foreground text-sm">
              The agent pipeline is standing by. Send a message to begin.
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            <Link href="/run" className={cn(buttonVariants({ size: "sm" }), "gap-1.5")}>
              <MessageSquare className="h-3.5 w-3.5" aria-hidden />
              Run
            </Link>
            <Link href="/knowledge" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "gap-1.5")}>
              <ScrollText className="h-3.5 w-3.5" aria-hidden />
              Knowledge
            </Link>
            <Link href="/onboarding" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "gap-1.5")}>
              <BookOpen className="h-3.5 w-3.5" aria-hidden />
              Setup guide
            </Link>
          </div>
        </Card>

        {/* Pending proposals */}
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="h-4 w-4 text-flow-thinking" aria-hidden />
              Curator notes
              {proposals.length > 0 && (
                <Badge
                  variant="outline"
                  className="ml-auto h-5 rounded-full border-flow-thinking/30 bg-flow-thinking/10 px-2 py-0 text-[10px]"
                >
                  {proposals.length} pending
                </Badge>
              )}
            </CardTitle>
            <CardDescription className="text-[13px]">
              The curator flags low-confidence runs with improvement proposals.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {proposals.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No pending proposals. Run the agent and submit low-score feedback to generate curator suggestions.
              </p>
            ) : (
              <ul className="space-y-2">
                {proposals.slice(0, 4).map((p) => (
                  <li
                    key={p.id}
                    className="rounded-lg border border-border/50 bg-muted/10 px-3 py-2 text-xs leading-snug"
                  >
                    <p className="font-medium text-foreground line-clamp-1">{p.title}</p>
                    <p className="mt-0.5 line-clamp-2 text-muted-foreground">{p.body}</p>
                  </li>
                ))}
                {proposals.length > 4 && (
                  <Link
                    href="/proposals"
                    className="block text-center text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    +{proposals.length - 4} more →
                  </Link>
                )}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
