"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, Brain, Loader2, MessageSquare } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
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
      <div className="flex items-center gap-2 text-muted-foreground text-sm">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Loading memory…
      </div>
    );
  }

  if (err) {
    return (
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
    );
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-8 pb-10">
      <FlowPageHeader
        leading={<Brain className="h-8 w-8 opacity-90" aria-hidden />}
        title="Memory"
        description="Episodic summaries are captured after successful runs. Semantic entries are stored vectors you add below (or promoted from high-quality feedback)."
      />

      <Card>
        <CardHeader className="space-y-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
            <div className="space-y-2">
              <Label>Agent</Label>
              <Select value={agentId ?? undefined} onValueChange={(v) => v != null && setAgentId(v)}>
                <SelectTrigger className="w-full sm:w-[280px]">
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
              className={cn(buttonVariants({ variant: "outline", size: "sm" }), "inline-flex gap-1.5")}
            >
              <MessageSquare className="h-3.5 w-3.5" aria-hidden />
              Run to add episodic
            </Link>
          </div>
          <CardTitle className="text-lg">Tiers</CardTitle>
          <CardDescription className="text-[13px]">Switch tabs to browse episodic vs semantic memories.</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="episodic">
            <TabsList className="grid w-full max-w-md grid-cols-2">
              <TabsTrigger value="episodic">Episodic</TabsTrigger>
              <TabsTrigger value="semantic">Semantic</TabsTrigger>
            </TabsList>
            <TabsContent value="episodic" className="mt-4 space-y-3">
              {loadingMem ? (
                <p className="text-sm text-muted-foreground">Loading…</p>
              ) : episodic.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No episodic memories yet. Complete a run from Run — summaries are saved automatically when the
                  pipeline finishes.
                </p>
              ) : (
                <ul className="space-y-3">
                  {episodic.map((m) => (
                    <MemoryCard key={m.id} entry={m} tier="episodic" />
                  ))}
                </ul>
              )}
            </TabsContent>
            <TabsContent value="semantic" className="mt-4 space-y-6">
              <div className="space-y-2">
                <Label htmlFor="mem-in">Add semantic memory</Label>
                <Textarea
                  id="mem-in"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={4}
                  placeholder="Paste a fact or preference to embed for this agent…"
                  className="text-sm"
                />
                <Button type="button" disabled={saving || !draft.trim()} onClick={() => void saveSemantic()}>
                  {saving ? "Saving…" : "Save"}
                </Button>
                {saveMsg ? (
                  <p
                    className={cn(
                      "text-sm",
                      saveMsg.startsWith("Saved") ? "text-muted-foreground" : "text-destructive",
                    )}
                    role="status"
                  >
                    {saveMsg}
                  </p>
                ) : null}
              </div>
              {loadingMem ? (
                <p className="text-sm text-muted-foreground">Loading…</p>
              ) : semantic.length === 0 ? (
                <p className="text-sm text-muted-foreground">No semantic memories yet. Add text above to store one.</p>
              ) : (
                <ul className="space-y-3">
                  {semantic.map((m) => (
                    <MemoryCard key={m.id} entry={m} tier="semantic" />
                  ))}
                </ul>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}

function MemoryCard({ entry, tier }: { entry: MemoryEntry; tier: "episodic" | "semantic" }) {
  return (
    <li
      className={cn(
        "rounded-lg border p-4 text-sm leading-relaxed",
        tier === "semantic"
          ? "border-flow-done/30 bg-flow-done/5"
          : "border-border/60 bg-muted/15",
      )}
    >
      <p className="text-foreground/90">{entry.content}</p>
      {entry.execution_id ? (
        <p className="mt-2 font-mono text-[10px] text-muted-foreground">run {entry.execution_id.slice(0, 8)}…</p>
      ) : null}
      {entry.created_at ? (
        <time dateTime={entry.created_at} className="mt-1 block text-[11px] text-muted-foreground">
          {new Date(entry.created_at).toLocaleString()}
        </time>
      ) : null}
    </li>
  );
}
