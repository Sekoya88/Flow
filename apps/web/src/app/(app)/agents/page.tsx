"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  BarChart2,
  Bot,
  Brain,
  CheckCircle2,
  Clock,
  Database,
  GitCompare,
  LayoutGrid,
  Loader2,
  Plus,
  Search,
  Sparkles,
  Table2,
  Target,
  Workflow,
  XCircle,
  Zap,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { AgentCard, type AgentRow } from "@/components/agents/AgentCard";
import { AgentDetailDrawer } from "@/components/agents/AgentDetailDrawer";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { ApiError, apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { logger } from "@/lib/logger";
import { agentDisplayName, cn } from "@/lib/utils";

type Me = { workspaces: { id: string; name: string }[] };

type CockpitAgent = AgentRow & {
  total_runs: number;
  last_run_at: string | null;
  last_status: string | null;
  episodic_memory_count: number;
  skills_count: number;
  enabled_tools: string[];
};

const TOOL_ICONS: Record<string, React.ReactNode> = {
  retrieve: <Database className="h-3 w-3" />,
  long_term_memory: <Brain className="h-3 w-3" />,
  tavily_search: <Zap className="h-3 w-3" />,
  sandbox: <Target className="h-3 w-3" />,
};

function StatusDot({ status }: { status: string | null }) {
  if (status === "completed") return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />;
  if (status === "failed") return <XCircle className="h-3.5 w-3.5 text-destructive" />;
  if (status === "running") return <Loader2 className="h-3.5 w-3.5 animate-spin text-flow-violet" />;
  return <div className="h-2 w-2 rounded-full bg-flow-700" />;
}

function CockpitRow({ a, onClick }: { a: CockpitAgent; onClick: () => void }) {
  const timeAgo = a.last_run_at
    ? (() => {
        const diff = Date.now() - new Date(a.last_run_at).getTime();
        const m = Math.floor(diff / 60000);
        if (m < 60) return `${m}m ago`;
        const h = Math.floor(m / 60);
        if (h < 24) return `${h}h ago`;
        return `${Math.floor(h / 24)}d ago`;
      })()
    : "—";

  return (
    <button
      type="button"
      onClick={onClick}
      className="grid w-full grid-cols-[1fr_80px_80px_80px_100px_120px] items-center gap-4 rounded-lg border border-flow-800 bg-card px-4 py-3 text-left text-xs transition-all hover:border-flow-violet/40 hover:bg-flow-violet/[0.04]"
    >
      {/* Name + template */}
      <div className="min-w-0">
        <p className="truncate font-medium text-foreground">{agentDisplayName(a)}</p>
        <p className="mt-0.5 truncate font-mono text-[10px] text-muted-foreground">{a.template}</p>
      </div>
      {/* Status */}
      <div className="flex items-center gap-1.5">
        <StatusDot status={a.last_status} />
        <span className="text-muted-foreground capitalize">{a.last_status ?? "—"}</span>
      </div>
      {/* Last run */}
      <div className="flex items-center gap-1 text-muted-foreground">
        <Clock className="h-3 w-3 shrink-0" />
        {timeAgo}
      </div>
      {/* Runs */}
      <div className="tabular-nums text-foreground/70">{a.total_runs}</div>
      {/* Memory */}
      <div className="flex items-center gap-1 text-muted-foreground">
        <Brain className="h-3 w-3 shrink-0" />
        <span>{a.episodic_memory_count} episodic</span>
      </div>
      {/* Tools */}
      <div className="flex items-center gap-1">
        {a.enabled_tools.slice(0, 4).map((t) => (
          <span
            key={t}
            title={t}
            className="flex h-5 w-5 items-center justify-center rounded border border-flow-800 bg-flow-900 text-muted-foreground"
          >
            {TOOL_ICONS[t] ?? <Zap className="h-3 w-3" />}
          </span>
        ))}
        {a.skills_count > 0 && (
          <Badge variant="outline" className="h-5 gap-0.5 rounded px-1.5 py-0 font-mono text-[9px] border-flow-violet/30 text-flow-violet">
            <Sparkles className="h-2.5 w-2.5" />
            {a.skills_count}
          </Badge>
        )}
      </div>
    </button>
  );
}

export default function AgentsPage() {
  const router = useRouter();
  const routerRef = useRef(router);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [wsId, setWsId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [selectedAgent, setSelectedAgent] = useState<AgentRow | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [view, setView] = useState<"grid" | "cockpit">("grid");
  const [cockpitAgents, setCockpitAgents] = useState<CockpitAgent[]>([]);
  const [cockpitLoading, setCockpitLoading] = useState(false);

  useEffect(() => {
    routerRef.current = router;
  }, [router]);

  const load = useCallback(() => {
    if (!getToken()) {
      routerRef.current.replace("/login");
      return;
    }
    setLoading(true);
    setErr(null);
    apiFetch<Me>("/api/v1/auth/me")
      .then((me) => {
        const w = me.workspaces[0];
        if (!w) {
          setErr("No workspace for this account.");
          return null;
        }
        setWsId(w.id);
        return apiFetch<{ agents: AgentRow[] }>(`/api/v1/workspaces/${w.id}/agents`);
      })
      .then((a) => {
        if (a?.agents) setAgents(a.agents);
      })
      .catch((e) => {
        setErr(e instanceof ApiError ? `${e.status}: ${e.body}` : "Could not load agents.");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    if (!search.trim()) return agents;
    const q = search.toLowerCase();
    return agents.filter(
      (a) =>
        a.name?.toLowerCase().includes(q) ||
        a.template?.toLowerCase().includes(q),
    );
  }, [agents, search]);

  const handleToolToggle = useCallback(
    async (agentId: string, tool: string, enabled: boolean) => {
      await apiFetch(`/api/v1/agents/${agentId}`, {
        method: "PATCH",
        json: { [tool]: enabled },
      });
      if (wsId) {
        try {
          const a = await apiFetch<{ agents: AgentRow[] }>(
            `/api/v1/workspaces/${wsId}/agents`,
          );
          if (a?.agents) {
            setAgents(a.agents);
            const updated = a.agents.find((x) => x.id === agentId);
            if (updated) setSelectedAgent(updated);
          }
        } catch {
          // Refresh failure is non-critical — PATCH already persisted
        }
      }
    },
    [wsId],
  );

  const loadCockpit = useCallback(async (id: string) => {
    setCockpitLoading(true);
    try {
      const r = await apiFetch<{ agents: CockpitAgent[] }>(`/api/v1/workspaces/${id}/cockpit`);
      setCockpitAgents(r.agents ?? []);
    } catch {
      setCockpitAgents([]);
    } finally {
      setCockpitLoading(false);
    }
  }, []);

  useEffect(() => {
    if (view === "cockpit" && wsId) {
      void loadCockpit(wsId);
    }
  }, [view, wsId, loadCockpit]);

  const openAgent = useCallback((agent: AgentRow) => {
    setSelectedAgent(agent);
    setDrawerOpen(true);
  }, []);

  const handleDelete = useCallback(async (agentId: string) => {
    await apiFetch(`/api/v1/agents/${agentId}`, { method: "DELETE" });
    setAgents((prev) => prev.filter((a) => a.id !== agentId));
  }, []);

  if (err) {
    return (
      <div className="mx-auto w-full max-w-6xl px-4 py-8">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Unable to load agents</AlertTitle>
          <AlertDescription className="flex items-center gap-2">
            <span>{err}</span>
            <Button size="sm" variant="outline" onClick={load}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-8 px-4 pb-10 animate-fade-in">
      {/* Header */}
      <FlowPageHeader
        eyebrow={
          <Badge
            variant="outline"
            className="gap-1 font-mono text-[10px] uppercase tracking-wide"
          >
            <Bot className="h-3 w-3" aria-hidden />
            Catalog
          </Badge>
        }
        title="Agents"
        description="Your workspace agents — each with its own template, tools, and learned skills. Click an agent to configure or run it."
        actions={
          <div className="flex items-center gap-2">
            <Link
              href="/agents/ab-test"
              className={cn(buttonVariants({ variant: "outline", size: "sm" }), "gap-1.5")}
            >
              <GitCompare className="h-3.5 w-3.5" aria-hidden />
              A/B Tests
            </Link>
            <Link
              href="/agents/new"
              className={cn(buttonVariants({ size: "default" }), "gap-1.5")}
            >
              <Plus className="h-4 w-4" aria-hidden />
              New agent
            </Link>
          </div>
        }
      />

      {/* Search + stats + view toggle */}
      {!loading && agents.length > 0 && (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative max-w-sm flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/50" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search agents…"
              className="pl-9 h-9 text-sm"
            />
          </div>
          <div className="flex items-center gap-2">
            <p className="text-xs text-muted-foreground tabular-nums">
              {filtered.length} of {agents.length} agent{agents.length !== 1 ? "s" : ""}
            </p>
            <div className="flex rounded-lg border border-flow-800 bg-card p-0.5">
              <button
                type="button"
                onClick={() => setView("grid")}
                className={cn("flex items-center gap-1 rounded-md px-2.5 py-1 text-xs transition-colors", view === "grid" ? "bg-flow-violet/20 text-flow-violet" : "text-muted-foreground hover:text-foreground")}
              >
                <LayoutGrid className="h-3.5 w-3.5" /> Grid
              </button>
              <button
                type="button"
                onClick={() => setView("cockpit")}
                className={cn("flex items-center gap-1 rounded-md px-2.5 py-1 text-xs transition-colors", view === "cockpit" ? "bg-flow-violet/20 text-flow-violet" : "text-muted-foreground hover:text-foreground")}
              >
                <Table2 className="h-3.5 w-3.5" /> Cockpit
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton key={i} className="h-44 rounded-[6px]" />
          ))}
        </div>
      ) : agents.length === 0 ? (
        /* Empty state */
        <div className="flex flex-col items-center gap-6 py-20">
          <div className="rounded-[6px] border border-flow-800 bg-card p-10 flex flex-col items-center gap-5 max-w-sm">
            <div className="relative">
              <div className="flex h-16 w-16 items-center justify-center rounded-[6px] bg-flow-violet/10 border border-flow-violet/20">
                <Bot className="h-8 w-8 text-flow-violet/60" />
              </div>
              <div className="absolute -right-1 -top-1 flex h-6 w-6 items-center justify-center rounded-full bg-flow-violet border border-background">
                <Sparkles className="h-3 w-3 text-white" />
              </div>
            </div>
            <div className="text-center space-y-2">
              <p className="text-base font-semibold text-foreground">Create your first agent</p>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Describe what you want your agent to do, and we&apos;ll configure the right template and tools automatically.
              </p>
            </div>
            <Link
              href="/agents/new"
              className={cn(buttonVariants({ size: "lg" }), "gap-2 w-full")}
            >
              <Sparkles className="h-4 w-4" />
              Create with vibe
            </Link>
          </div>
        </div>
      ) : filtered.length === 0 ? (
        /* No search results */
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <Search className="h-8 w-8 text-muted-foreground/30" />
          <p className="text-sm text-muted-foreground">
            No agents match &ldquo;{search}&rdquo;
          </p>
          <Button variant="ghost" size="sm" onClick={() => setSearch("")}>
            Clear search
          </Button>
        </div>
      ) : view === "cockpit" ? (
        /* Cockpit table view */
        <div className="space-y-1.5">
          {/* Column headers */}
          <div className="grid grid-cols-[1fr_80px_80px_80px_100px_120px] items-center gap-4 px-4 pb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60">
            <span>Agent</span>
            <span>Status</span>
            <span>Last run</span>
            <span>Runs</span>
            <span>Memory</span>
            <span>Tools</span>
          </div>
          {cockpitLoading ? (
            Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[52px] rounded-lg" />)
          ) : cockpitAgents.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">No cockpit data — run an agent first.</p>
          ) : (
            cockpitAgents.map((a) => (
              <CockpitRow key={a.id} a={a} onClick={() => openAgent(a)} />
            ))
          )}
        </div>
      ) : (
        /* Agent card grid */
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((agent, i) => (
            <div
              key={agent.id}
              className="animate-slide-up"
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <AgentCard agent={agent} onClick={() => openAgent(agent)} />
            </div>
          ))}
        </div>
      )}

      {/* Detail drawer */}
      <AgentDetailDrawer
        agent={selectedAgent}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        onToolToggle={handleToolToggle}
        onDelete={handleDelete}
        workspaceId={wsId}
      />
    </div>
  );
}
