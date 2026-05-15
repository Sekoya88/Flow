"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, Brain, Clock, Loader2, MessageSquare, Sparkles } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState } from "@/components/ui/empty-state";
import { AnimatedList } from "@/components/ui/animated-list";
import { ApiError, apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Me = { workspaces: { id: string; name: string }[] };

type AgentRow = { id: string; name: string; template: string };

type MemoryEntry = {
  id: string;
  content: string;
  created_at?: string;
  execution_id?: string | null;
};

export default function MemoryPage() {
  const router = useRouter();
  const routerRef = useRef(router);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [wsId, setWsId] = useState<string | null>(null);
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [agentId, setAgentId] = useState<string | null>(null);
  const [episodic, setEpisodic] = useState<MemoryEntry[]>([]);
  const [semantic, setSemantic] = useState<MemoryEntry[]>([]);
  const [loadingMem, setLoadingMem] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  useEffect(() => {
    routerRef.current = router;
  }, [router]);

  useEffect(() => {
    if (!getToken()) {
      routerRef.current.replace("/login");
      return;
    }
    setLoading(true);
    apiFetch<Me>("/api/v1/auth/me")
      .then((m) => {
        const w = m.workspaces[0];
        if (!w) {
          setErr("No workspace for this account.");
          return;
        }
        setWsId(w.id);
        return apiFetch<{ agents: AgentRow[] }>(`/api/v1/workspaces/${w.id}/agents`);
      })
      .then((a) => {
        if (!a?.agents?.length) {
          setErr("No agent in workspace.");
          return;
        }
        setAgents(a.agents);
        setAgentId(a.agents[0].id);
      })
      .catch((e) => {
        setErr(e instanceof ApiError ? `${e.status}: ${e.body}` : "Could not load account.");
      })
      .finally(() => setLoading(false));
  }, []);

  const loadTiered = useCallback(async (wid: string, aid: string) => {
    setLoadingMem(true);
    try {
      const r = await apiFetch<{ episodic: MemoryEntry[]; semantic: MemoryEntry[] }>(
        `/api/v1/memory/tiered?workspace_id=${wid}&agent_id=${aid}`,
      );
      setEpisodic(r.episodic ?? []);
      setSemantic(r.semantic ?? []);
    } catch {
      setEpisodic([]);
      setSemantic([]);
    } finally {
      setLoadingMem(false);
    }
  }, []);

  useEffect(() => {
    if (!wsId || !agentId) return;
    void loadTiered(wsId, agentId);
  }, [wsId, agentId, loadTiered]);

  async function saveSemantic() {
    if (!wsId || !agentId || !draft.trim()) return;
    setSaving(true);
    setSaveMsg(null);
    try {
      await apiFetch("/api/v1/memory", {
        method: "POST",
        json: { workspace_id: wsId, agent_id: agentId, content: draft.trim() },
      });
      setDraft("");
      await loadTiered(wsId, agentId);
      setSaveMsg("Saved to semantic memory.");
    } catch (e) {
      setSaveMsg(e instanceof ApiError ? `${e.status}: ${e.body}` : String(e));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto flex max-w-4xl items-center gap-2 px-4 py-16 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Loading memory…
      </div>
    );
  }

  if (err) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-10">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Memory unavailable</AlertTitle>
          <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <span>{err}</span>
            <Link href="/run" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
              Open Run
            </Link>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-8 px-4 pb-12 pt-6 animate-fade-in">
      {/* Brand header */}
      <header className="space-y-2">
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-flow-brand" />
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-flow-brand/80">
            Memory
          </span>
        </div>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          What your agents remember
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground leading-relaxed">
          Episodic summaries are captured after successful runs. Semantic entries are stored
          vectors you add below (or promoted from high-quality feedback).
        </p>
      </header>

      {/* Agent picker */}
      <section className="surface-glass flex flex-col gap-4 rounded-2xl border border-border/50 p-5 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-2">
          <Label className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/80">
            <Sparkles className="h-3 w-3 text-flow-brand" />
            Agent
          </Label>
          <Select value={agentId ?? undefined} onValueChange={(v) => v != null && setAgentId(v)}>
            <SelectTrigger className="w-full bg-card/60 sm:w-[280px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {agents.map((a) => (
                <SelectItem key={a.id} value={a.id}>
                  {a.name || a.template}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Link
          href="/run"
          className={cn(
            buttonVariants({ variant: "outline", size: "sm" }),
            "inline-flex gap-1.5 self-start sm:self-end",
          )}
        >
          <MessageSquare className="h-3.5 w-3.5" aria-hidden />
          Run to add episodic
        </Link>
      </section>

      {/* Tiers */}
      <Tabs defaultValue="episodic">
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="episodic">Episodic</TabsTrigger>
          <TabsTrigger value="semantic">Semantic</TabsTrigger>
        </TabsList>

        <TabsContent value="episodic" className="mt-5 space-y-4">
          {loadingMem ? (
            <SkeletonGrid />
          ) : episodic.length === 0 ? (
            <EmptyState
              icon={Brain}
              tone="muted"
              title="No episodic memories yet"
              description="Episodic summaries are saved automatically when a Run pipeline finishes. Kick off one to populate this tier."
              action={
                <Link
                  href="/run"
                  className={cn(buttonVariants({ size: "sm" }), "gap-1.5")}
                >
                  <MessageSquare className="h-3.5 w-3.5" />
                  Open Run
                </Link>
              }
            />
          ) : (
            <AnimatedList className="space-y-3">
              {episodic.map((m) => (
                <MemoryCard key={m.id} entry={m} tier="episodic" />
              ))}
            </AnimatedList>
          )}
        </TabsContent>

        <TabsContent value="semantic" className="mt-5 space-y-6">
          {/* Add */}
          <div className="surface-glass space-y-3 rounded-2xl border border-border/50 p-5">
            <Label htmlFor="mem-in" className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/80">
              Add semantic memory
            </Label>
            <Textarea
              id="mem-in"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={3}
              placeholder="Paste a fact or preference to embed for this agent…"
              className="resize-none rounded-xl border-border/60 bg-card/60 text-sm focus-visible:border-flow-brand/50 focus-visible:ring-flow-brand/30"
            />
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11px] font-mono text-muted-foreground/60">
                Stored as a vector for retrieval at planner-time
              </p>
              <Button
                type="button"
                disabled={saving || !draft.trim()}
                onClick={() => void saveSemantic()}
                className="gap-1.5 bg-flow-brand text-white hover:bg-flow-brand/90"
              >
                {saving ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Saving…
                  </>
                ) : (
                  "Save"
                )}
              </Button>
            </div>
            {saveMsg && (
              <p
                className={cn(
                  "rounded-lg px-3 py-2 text-xs animate-fade-in",
                  saveMsg.startsWith("Saved")
                    ? "border border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                    : "border border-destructive/30 bg-destructive/10 text-destructive",
                )}
                role="status"
              >
                {saveMsg}
              </p>
            )}
          </div>

          {/* List */}
          {loadingMem ? (
            <SkeletonGrid />
          ) : semantic.length === 0 ? (
            <EmptyState
              icon={Sparkles}
              tone="brand"
              title="No semantic memories yet"
              description="Add a fact above, or let the curator promote high-quality observations from completed runs."
            />
          ) : (
            <AnimatedList className="space-y-3">
              {semantic.map((m) => (
                <MemoryCard key={m.id} entry={m} tier="semantic" />
              ))}
            </AnimatedList>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function SkeletonGrid() {
  return (
    <div className="space-y-3">
      {[0, 1, 2, 3].map((i) => (
        <Skeleton key={i} className="h-20 w-full rounded-xl" />
      ))}
    </div>
  );
}

function MemoryCard({ entry, tier }: { entry: MemoryEntry; tier: "episodic" | "semantic" }) {
  return (
    <article
      className={cn(
        "surface-glass group rounded-xl border p-4 text-sm leading-relaxed transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md",
        tier === "semantic"
          ? "border-flow-brand/25 hover:border-flow-brand/50 hover:shadow-flow-brand/10"
          : "border-border/50 hover:border-flow-brand/30",
      )}
    >
      <p className="text-foreground/90">{entry.content}</p>
      <div className="mt-3 flex items-center gap-3 text-[11px]">
        {entry.execution_id && (
          <span className="font-mono text-muted-foreground/70">
            run {entry.execution_id.slice(0, 8)}…
          </span>
        )}
        {entry.execution_id && entry.created_at && (
          <span className="text-muted-foreground/30">·</span>
        )}
        {entry.created_at && (
          <span className="flex items-center gap-1 text-muted-foreground/70">
            <Clock className="h-3 w-3" />
            {new Date(entry.created_at).toLocaleString()}
          </span>
        )}
        <span className="ml-auto font-mono text-[10px] uppercase tracking-wider text-muted-foreground/40 transition-colors group-hover:text-flow-brand/70">
          {tier}
        </span>
      </div>
    </article>
  );
}
