"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  BarChart2,
  Bot,
  GitCompare,
  Loader2,
  Plus,
  Search,
  Sparkles,
  Target,
  Workflow,
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
import { cn } from "@/lib/utils";

type Me = { workspaces: { id: string; name: string }[] };

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
      try {
        await apiFetch(`/api/v1/agents/${agentId}`, {
          method: "PATCH",
          json: { [tool]: enabled },
        });
        // Refresh agent list
        if (wsId) {
          const a = await apiFetch<{ agents: AgentRow[] }>(
            `/api/v1/workspaces/${wsId}/agents`,
          );
          if (a?.agents) {
            setAgents(a.agents);
            // Update selected agent
            const updated = a.agents.find((x) => x.id === agentId);
            if (updated) setSelectedAgent(updated);
          }
        }
      } catch (e) {
        console.warn("tool toggle failed", e);
      }
    },
    [wsId],
  );

  const openAgent = useCallback((agent: AgentRow) => {
    setSelectedAgent(agent);
    setDrawerOpen(true);
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
              className={cn(buttonVariants({ size: "default" }), "gap-1.5 shadow-sm")}
            >
              <Plus className="h-4 w-4" aria-hidden />
              New agent
            </Link>
          </div>
        }
      />

      {/* Search + stats bar */}
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
          <p className="text-xs text-muted-foreground tabular-nums">
            {filtered.length} of {agents.length} agent{agents.length !== 1 ? "s" : ""}
          </p>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton key={i} className="h-44 rounded-2xl" />
          ))}
        </div>
      ) : agents.length === 0 ? (
        /* Empty state */
        <div className="flex flex-col items-center gap-6 py-20">
          <div className="rounded-2xl border border-border/40 bg-card/60 backdrop-blur-sm p-10 flex flex-col items-center gap-5 max-w-sm">
            <div className="relative">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-flow-brand/10 border border-flow-brand/20">
                <Bot className="h-8 w-8 text-flow-brand/60" />
              </div>
              <div className="absolute -right-1 -top-1 flex h-6 w-6 items-center justify-center rounded-full bg-flow-brand border border-background">
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
      />
    </div>
  );
}
