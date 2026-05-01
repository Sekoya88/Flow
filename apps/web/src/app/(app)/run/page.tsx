"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, Brain, Check, ChevronDown, Loader2 } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { FlowGraph } from "@/components/flow/FlowGraph";
import { TokenStream } from "@/components/flow/TokenStream";
import { AgentTimeline, type ExecRow } from "@/components/flow/AgentTimeline";
import { MemoryDrawer } from "@/components/flow/MemoryDrawer";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { ApiError, apiFetch, getApiBase } from "@/lib/api";
import { track } from "@/lib/analytics";
import { getToken } from "@/lib/auth";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";

type Me = {
  workspaces: { id: string; name: string }[];
};

type AgentRow = { id: string; name: string; template: string; config: Record<string, unknown> };

type Agents = { agents: AgentRow[] };

type ToolFlags = { retrieve: boolean; sandbox: boolean; long_term_memory: boolean };

type RunPrefs = { message: string; tools: ToolFlags; agentId: string };

function runPrefsKey(ws: string) {
  return `flow.run.prefs.${ws}`;
}

function loadRunPrefs(ws: string): Partial<RunPrefs> | null {
  try {
    const raw = localStorage.getItem(runPrefsKey(ws));
    if (!raw) return null;
    return JSON.parse(raw) as Partial<RunPrefs>;
  } catch {
    return null;
  }
}

function saveRunPrefs(ws: string, prefs: RunPrefs) {
  try {
    localStorage.setItem(runPrefsKey(ws), JSON.stringify(prefs));
  } catch {
    /* quota */
  }
}

const DEFAULT_TOOLS: ToolFlags = {
  retrieve: true,
  sandbox: true,
  long_term_memory: true,
};

function readTools(cfg: Record<string, unknown> | undefined): ToolFlags {
  const t = cfg?.tools;
  if (!t || typeof t !== "object" || Array.isArray(t)) return { ...DEFAULT_TOOLS };
  const o = t as Record<string, unknown>;
  return {
    retrieve: o.retrieve !== false,
    sandbox: o.sandbox !== false,
    long_term_memory: o.long_term_memory !== false,
  };
}

function agentDisplayName(a: AgentRow | undefined): string {
  if (!a) return "Agent";
  const n = (a.name ?? "").trim();
  if (n) return n;
  const t = (a.template ?? "").trim().replace(/_/g, " ");
  if (t) return t;
  return `Agent ${a.id.slice(0, 8)}…`;
}

const TOOL_ROWS: { key: keyof ToolFlags; title: string; desc: string }[] = [
  {
    key: "retrieve",
    title: "Knowledge search",
    desc: "Pull relevant snippets from workspace sources before answering.",
  },
  {
    key: "sandbox",
    title: "Python sandbox",
    desc: "When the model emits a fenced python block, run it in an isolated runner.",
  },
  {
    key: "long_term_memory",
    title: "Long-term memory",
    desc: "Recall past saved memories for you with this agent.",
  },
];

const TRACE_VERBOSE_KEY = "flow.run.traceVerbose";

function loadTraceVerbose(): boolean {
  try {
    return localStorage.getItem(TRACE_VERBOSE_KEY) === "1";
  } catch {
    return false;
  }
}

function persistTraceVerbose(verbose: boolean) {
  try {
    localStorage.setItem(TRACE_VERBOSE_KEY, verbose ? "1" : "0");
  } catch {
    /* quota */
  }
}

const TRACE_MAX_LINES = 500;
const TRACE_TRUNC = 2800;
const TOKEN_TRACE_TRUNC = 480;

function truncateTraceText(s: string, max: number): string {
  if (s.length <= max) return s;
  return `${s.slice(0, max)}… (+${s.length - max} chars)`;
}

function formatTracePayload(payload: unknown): string {
  try {
    return truncateTraceText(JSON.stringify(payload, null, 2), TRACE_TRUNC);
  } catch {
    return truncateTraceText(String(payload), TRACE_TRUNC);
  }
}

type SseEvent = {
  kind: string;
  node?: string;
  summary?: string;
  answer?: string;
  text?: string;
  message?: string;
  confidence?: number;
  payload?: { node?: string; partial?: unknown };
};

export default function RunPage() {
  const router = useRouter();
  const routerRef = useRef(router);

  // Per-field selectors — object selectors return a new ref each render and pin Zustand in a loop.
  const setNode = useStore((s) => s.setNode);
  const appendToken = useStore((s) => s.appendToken);
  const reset = useStore((s) => s.reset);
  const setActiveExecution = useStore((s) => s.setActiveExecution);
  const activeExecutionId = useStore((s) => s.activeExecutionId);
  const inspectorOpen = useStore((s) => s.inspectorOpen);
  const setInspectorOpen = useStore((s) => s.setInspectorOpen);

  const [wsId, setWsId] = useState<string | null>(null);
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [agentId, setAgentId] = useState<string | null>(null);
  const [message, setMessage] = useState("Summarize what Flow can do for me.");
  const [running, setRunning] = useState(false);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [loadingBoot, setLoadingBoot] = useState(true);
  const [tools, setTools] = useState<ToolFlags>({ ...DEFAULT_TOOLS });
  const [savingTools, setSavingTools] = useState(false);
  const [toolsSaved, setToolsSaved] = useState(false);
  const [lastExecutionId, setLastExecutionId] = useState<string | null>(null);
  const [feedbackPercent, setFeedbackPercent] = useState(70);
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackSending, setFeedbackSending] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);
  const [executions, setExecutions] = useState<ExecRow[]>([]);
  const [knowledgeCount, setKnowledgeCount] = useState<number | null>(null);
  const [agentRenameDraft, setAgentRenameDraft] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [traceLines, setTraceLines] = useState<string[]>([]);
  const traceBottomRef = useRef<HTMLDivElement>(null);
  const [traceVerbose, setTraceVerbose] = useState(false);
  const traceVerboseRef = useRef(false);

  const prefsDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeAgent = useMemo(() => agents.find((x) => x.id === agentId), [agents, agentId]);
  const activeAgentLabel = useMemo(() => agentDisplayName(activeAgent), [activeAgent]);

  useEffect(() => {
    routerRef.current = router;
  }, [router]);

  useEffect(() => {
    const v = loadTraceVerbose();
    traceVerboseRef.current = v;
    setTraceVerbose(v);
  }, []);

  useEffect(() => {
    traceVerboseRef.current = traceVerbose;
  }, [traceVerbose]);

  useEffect(() => {
    if (!getToken()) {
      routerRef.current.replace("/login");
      return;
    }
    setLoadingBoot(true);
    setLoadErr(null);
    let bootWorkspaceId = "";
    apiFetch<Me>("/api/v1/auth/me")
      .then((m) => {
        const w = m.workspaces[0];
        if (!w) { setLoadErr("No workspace."); return; }
        bootWorkspaceId = w.id;
        setWsId(w.id);
        return apiFetch<Agents>(`/api/v1/workspaces/${w.id}/agents`);
      })
      .then((a) => {
        if (!a) return;
        if (!a.agents?.length) { setLoadErr("No agent in workspace."); return; }
        setAgents(a.agents);
        const prefs = bootWorkspaceId ? loadRunPrefs(bootWorkspaceId) : null;
        const first = a.agents[0];
        const pick =
          prefs?.agentId && a.agents.some((x) => x.id === prefs.agentId) ? prefs.agentId : first.id;
        setAgentId(pick);
        const ag = a.agents.find((x) => x.id === pick) ?? first;
        setTools(
          prefs?.tools && typeof prefs.tools === "object"
            ? { ...DEFAULT_TOOLS, ...prefs.tools }
            : readTools(ag.config),
        );
        if (prefs?.message && prefs.message.trim()) setMessage(prefs.message);
      })
      .catch((e) => {
        setLoadErr(e instanceof ApiError ? `${e.status}: ${e.body}` : "Failed to load workspace or agents.");
      })
      .finally(() => setLoadingBoot(false));
  }, []);

  const onSelectAgent = useCallback((id: string) => {
    setAgentId(id);
    const ag = agents.find((x) => x.id === id);
    setTools(readTools(ag?.config));
    setToolsSaved(false);
    setAgentRenameDraft((ag?.name ?? "").trim());
  }, [agents]);

  useEffect(() => {
    if (!wsId || !getToken()) return;
    void apiFetch<{ executions: ExecRow[] }>(`/api/v1/workspaces/${wsId}/executions?limit=25`).then(
      (r) => setExecutions(r.executions),
      () => setExecutions([]),
    );
    void apiFetch<{ sources: unknown[] }>(`/api/v1/knowledge?workspace_id=${wsId}`).then(
      (r) => setKnowledgeCount(Array.isArray(r.sources) ? r.sources.length : 0),
      () => setKnowledgeCount(null),
    );
  }, [wsId, lastExecutionId]);

  useEffect(() => {
    setAgentRenameDraft((activeAgent?.name ?? "").trim());
  }, [activeAgent?.id, activeAgent?.name]);

  useEffect(() => {
    if (!wsId || !agentId) return;
    if (prefsDebounce.current) clearTimeout(prefsDebounce.current);
    prefsDebounce.current = setTimeout(() => {
      saveRunPrefs(wsId, { message, tools, agentId });
    }, 500);
    return () => { if (prefsDebounce.current) clearTimeout(prefsDebounce.current); };
  }, [wsId, agentId, message, tools]);

  const appendTraceLine = useCallback((line: string | null) => {
    if (line === null) return;
    const stamp = new Date().toISOString().slice(11, 23);
    setTraceLines((prev) => {
      const row = `[${stamp}] ${line}`;
      const next = [...prev, row];
      return next.length > TRACE_MAX_LINES ? next.slice(-TRACE_MAX_LINES) : next;
    });
    queueMicrotask(() => {
      traceBottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    });
  }, []);

  const onTraceVerboseChange = useCallback((checked: boolean) => {
    traceVerboseRef.current = checked;
    setTraceVerbose(checked);
    persistTraceVerbose(checked);
  }, []);

  async function saveAgentDisplayName() {
    if (!agentId || !agentRenameDraft.trim()) return;
    setSavingName(true);
    try {
      await apiFetch(`/api/v1/agents/${agentId}`, {
        method: "PATCH",
        json: { name: agentRenameDraft.trim() },
      });
      const r = await apiFetch<Agents>(`/api/v1/workspaces/${wsId}/agents`);
      setAgents(r.agents);
      track("agent_renamed", { agent_id: agentId });
    } catch {
      // silent
    } finally {
      setSavingName(false);
    }
  }

  async function saveTools() {
    if (!agentId) return;
    setSavingTools(true);
    setToolsSaved(false);
    try {
      await apiFetch(`/api/v1/agents/${agentId}`, { method: "PATCH", json: tools });
      const r = await apiFetch<Agents>(`/api/v1/workspaces/${wsId}/agents`);
      setAgents(r.agents);
      track("agent_tools_saved", { agent_id: agentId });
      setToolsSaved(true);
      setTimeout(() => setToolsSaved(false), 2000);
    } catch {
      // silent
    } finally {
      setSavingTools(false);
    }
  }

  async function run() {
    if (!agentId || !getToken()) return;
    setRunning(true);
    reset();
    setTraceLines([]);
    setLastExecutionId(null);
    setFeedbackMsg(null);
    const apiBase = getApiBase();
    try {
      const res = await apiFetch<{ execution_id: string }>(`/api/v1/agents/${agentId}/execute`, {
        method: "POST",
        json: { message },
      });
      const eid = res.execution_id;
      setActiveExecution(eid);
      appendTraceLine(`execute accepted · execution_id=${eid}`);
      // Seed planner as "thinking" immediately
      setNode("planner", { status: "thinking" });
      track("run_started", { agent_id: agentId, execution_id: eid });

      const { stream_jwt } = await apiFetch<{ stream_jwt: string }>(
        `/api/v1/executions/${eid}/stream-token`,
        { method: "POST" },
      );
      const url = `${apiBase}/api/v1/executions/${eid}/stream?stream_jwt=${encodeURIComponent(stream_jwt)}`;
      appendTraceLine("SSE · connecting…");
      const es = new EventSource(url);

      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as SseEvent;
          const verbose = traceVerboseRef.current;

          if (data.kind === "node_update" && data.node) {
            const prev = ["planner", "worker", "synthesizer"];
            const idx = prev.indexOf(data.node);
            if (idx > 0) setNode(prev[idx - 1], { status: "done" });
            setNode(data.node, { status: "streaming" });
            appendTraceLine(
              verbose
                ? `node_update · ${data.node}\n${formatTracePayload(data.payload ?? {})}`
                : `graph · ${data.summary ?? data.node}`,
            );
          } else if (data.kind === "token" && data.text) {
            if (verbose) {
              appendTraceLine(
                `token · ${data.node ?? "?"}\n${truncateTraceText(data.text, TOKEN_TRACE_TRUNC)}`,
              );
            }
            appendToken(data.text);
          } else if (data.kind === "final" && data.answer) {
            appendTraceLine(
              verbose
                ? `final · confidence=${data.confidence ?? "?"}\n${truncateTraceText(data.answer, TRACE_TRUNC)}`
                : `final · ${data.answer.length} chars · confidence ${data.confidence ?? "?"}`,
            );
            appendToken(data.answer);
            setNode("synthesizer", { status: "done" });
          } else if (data.kind === "error") {
            appendTraceLine(`error · ${data.message ?? "unknown"}`);
            setNode("synthesizer", { status: "error" });
          } else if (data.kind === "done") {
            appendTraceLine("done · stream closed");
            es.close();
            setRunning(false);
            setActiveExecution(null);
            setLastExecutionId(eid);
            setFeedbackPercent(70);
            setFeedbackComment("");
            track("run_completed", { execution_id: eid, agent_id: agentId });
            if (wsId) {
              void apiFetch<{ executions: ExecRow[] }>(`/api/v1/workspaces/${wsId}/executions?limit=25`).then(
                (r) => setExecutions(r.executions),
              );
            }
          }
        } catch {
          appendTraceLine(traceVerboseRef.current ? "SSE · non-JSON line skipped" : "SSE · skipped frame");
        }
      };

      es.onerror = () => {
        appendTraceLine("SSE · connection error (closed or network)");
        es.close();
        setRunning(false);
        setActiveExecution(null);
        setNode("synthesizer", { status: "error" });
      };
    } catch (e) {
      appendTraceLine(`run failed · ${e instanceof ApiError ? `${e.status}: ${e.body}` : String(e)}`);
      setRunning(false);
      setActiveExecution(null);
      track("run_failed", { agent_id: agentId });
      void e;
    }
  }

  async function submitFeedback() {
    if (!lastExecutionId) return;
    setFeedbackSending(true);
    setFeedbackMsg(null);
    try {
      const r = await apiFetch<{ ok: boolean; proposal_id: string | null }>(
        `/api/v1/executions/${lastExecutionId}/feedback`,
        {
          method: "POST",
          json: {
            score: Math.round(feedbackPercent) / 100,
            comment: feedbackComment.trim() || null,
          },
        },
      );
      const extra = r.proposal_id ? ` A curator note was queued.` : "";
      setFeedbackMsg(`Thanks — feedback saved.${extra}`);
      track("feedback_sent", { execution_id: lastExecutionId, score: feedbackPercent });
    } catch (e) {
      setFeedbackMsg(e instanceof ApiError ? `${e.status}: ${e.body}` : String(e));
    } finally {
      setFeedbackSending(false);
    }
  }

  if (loadErr) {
    return (
      <div className="mx-auto w-full max-w-4xl space-y-6">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Run unavailable</AlertTitle>
          <AlertDescription>{loadErr}</AlertDescription>
        </Alert>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => router.push("/dashboard")}>
            Back to dashboard
          </Button>
          <Link
            href="/onboarding"
            className={cn(buttonVariants({ variant: "secondary", size: "sm" }), "inline-flex")}
          >
            Setup checklist
          </Link>
        </div>
      </div>
    );
  }

  if (loadingBoot || !wsId || !agentId) {
    return (
      <div className="mx-auto w-full max-w-4xl space-y-10">
        <div className="space-y-3">
          <Skeleton className="h-9 w-48" />
          <Skeleton className="h-4 w-full max-w-xl" />
        </div>
        <Skeleton className="h-32 w-full rounded-xl" />
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="space-y-10">
            <Skeleton className="h-72 w-full rounded-xl" />
            <Skeleton className="h-96 w-full rounded-xl" />
          </div>
          <div className="space-y-10">
            <Skeleton className="h-44 w-full rounded-xl" />
            <Skeleton className="h-72 w-full rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <MemoryDrawer open={memoryOpen} onOpenChange={setMemoryOpen} workspaceId={wsId} agentId={agentId} />

      <div className="mx-auto w-full max-w-4xl space-y-10 pb-8">
        <FlowPageHeader
          title="Run"
          description="Send a message to your workspace agent. Watch the graph execute step by step."
          actions={
            <Button
              variant="outline"
              size="sm"
              className="shrink-0 gap-1.5"
              onClick={() => setMemoryOpen(true)}
              title="Open memory drawer"
            >
              <Brain className="h-3.5 w-3.5 opacity-80" aria-hidden />
              Memory
            </Button>
          }
          meta={
            <>
              {knowledgeCount !== null ? (
                <Badge variant="secondary" className="h-7 rounded-full px-3">
                  Workspace sources: {knowledgeCount}
                </Badge>
              ) : null}
              <Link
                href="/knowledge"
                className={cn(buttonVariants({ variant: "outline", size: "sm" }), "inline-flex h-7")}
              >
                Manage knowledge
              </Link>
            </>
          }
        />

        <div className="rounded-xl border border-border/60 bg-card/60 px-4 py-6 shadow-sm backdrop-blur-sm">
          <FlowGraph className="mx-auto w-full max-w-sm" />
        </div>

        <details className="group rounded-lg border border-border/60 bg-muted/20 px-4 py-3 text-sm">
          <summary className="flex cursor-pointer list-none items-center gap-2 font-medium text-foreground outline-none [&::-webkit-details-marker]:hidden">
            <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
            Connection details · trace
          </summary>
          <div className="mt-3 space-y-3 text-muted-foreground text-xs leading-relaxed">
            <p>
              Live output uses Server-Sent Events with{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px] text-foreground/90">
                Last-Event-ID
              </code>{" "}
              reconnect. API base:{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px] text-foreground/90">
                {getApiBase()}
              </code>
            </p>
            <p className="text-[11px]">
              <strong className="text-foreground">LangSmith</strong> traces graph nodes when{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono">LANGCHAIN_API_KEY</code> is set; API logs stay at
              INFO unless <code className="rounded bg-muted px-1 py-0.5 font-mono">LOG_LEVEL=DEBUG</code>.
            </p>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="mb-0 font-medium text-foreground">Live trace</p>
              <div className="flex items-center gap-2">
                <span className={cn(!traceVerbose && "text-foreground")}>Concise</span>
                <Switch
                  checked={traceVerbose}
                  onCheckedChange={onTraceVerboseChange}
                  aria-label="Verbose SSE trace"
                />
                <span className={cn(traceVerbose && "text-foreground")}>Verbose</span>
              </div>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Concise: graph steps (server summaries), lifecycle, final size — no per-token lines. Verbose: raw node
              payloads and tokens.
            </p>
            <ScrollArea className="h-52 rounded-md border border-border/80 bg-background/80">
              <pre className="whitespace-pre-wrap break-words p-3 font-mono text-[11px] leading-snug text-foreground/90">
                {traceLines.length === 0
                  ? "Run a message — concise mode shows pipeline checkpoints only; toggle verbose for full SSE payloads."
                  : traceLines.join("\n\n")}
                <div ref={traceBottomRef} aria-hidden className="h-px w-full shrink-0" />
              </pre>
            </ScrollArea>
          </div>
        </details>

        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
          <div className="flex flex-col gap-10">
            {/* Message input */}
            <Card className="gap-6 py-6 shadow-sm">
              <CardHeader className="space-y-1 px-6">
                <CardTitle className="text-lg">Your message</CardTitle>
                <CardDescription className="text-[13px] leading-relaxed">
                  This is sent as the latest human turn. Each run is checkpointed so you can iterate safely.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 px-6">
                <Textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  rows={6}
                  className="min-h-[140px] resize-y text-[15px] leading-relaxed"
                />
                <div className="flex flex-wrap items-center gap-3">
                  <Button size="lg" onClick={() => void run()} disabled={running} className="min-w-[7rem]">
                    {running ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Running…
                      </>
                    ) : (
                      "Run"
                    )}
                  </Button>
                  {running && (
                    <span className="text-muted-foreground text-sm">Streaming in progress…</span>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Token stream output */}
            <Card className="gap-6 py-6 shadow-sm">
              <CardHeader className="space-y-1 px-6">
                <CardTitle className="text-lg">Output</CardTitle>
                <CardDescription className="text-[13px] leading-relaxed">
                  Tokens stream live. The final answer builds character by character.
                </CardDescription>
              </CardHeader>
              <CardContent className="px-6">
                <ScrollArea className="h-[min(28rem,55vh)] rounded-lg border border-border bg-muted/15">
                  <div className="p-4">
                    <TokenStream
                      placeholder="Nothing yet — run a message to see planner → worker → synthesizer output stream here."
                    />
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            {/* Feedback */}
            {lastExecutionId ? (
              <Card className="gap-6 py-6 shadow-sm">
                <CardHeader className="space-y-1 px-6">
                  <CardTitle className="text-lg">How was this run?</CardTitle>
                  <CardDescription className="text-[13px] leading-relaxed">
                    Your score helps tune the workspace. Very low scores may enqueue a curator suggestion — check{" "}
                    <span className="text-foreground/90">Proposals</span> after a poor run.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5 px-6">
                  <p className="text-muted-foreground text-xs">
                    Run id{" "}
                    <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px]">{lastExecutionId}</code>
                  </p>
                  <div className="space-y-3">
                    <div className="flex justify-between text-sm">
                      <Label htmlFor="fb-score">Quality</Label>
                      <span className="text-muted-foreground tabular-nums">{feedbackPercent}%</span>
                    </div>
                    <Slider
                      id="fb-score"
                      min={0}
                      max={100}
                      value={[feedbackPercent]}
                      onValueChange={(v) => {
                        const n = Array.isArray(v) ? v[0] : v;
                        setFeedbackPercent(typeof n === "number" ? n : 0);
                      }}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="fb-comment">Notes (optional)</Label>
                    <Textarea
                      id="fb-comment"
                      value={feedbackComment}
                      onChange={(e) => setFeedbackComment(e.target.value)}
                      rows={3}
                      className="text-sm"
                      placeholder="What worked or felt off?"
                    />
                  </div>
                  <Button type="button" disabled={feedbackSending} onClick={() => void submitFeedback()}>
                    {feedbackSending ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Sending…
                      </>
                    ) : (
                      "Send feedback"
                    )}
                  </Button>
                  {feedbackMsg ? (
                    <p
                      className={cn(
                        "text-sm",
                        feedbackMsg.startsWith("Thanks") ? "text-muted-foreground" : "text-destructive",
                      )}
                      role="status"
                    >
                      {feedbackMsg}
                    </p>
                  ) : null}
                </CardContent>
              </Card>
            ) : null}
          </div>

          {/* Right column inspector */}
          <aside className="flex flex-col gap-10 lg:sticky lg:top-24">
            {/* Inspector collapse toggle */}
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Inspector</span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-[11px] text-muted-foreground"
                onClick={() => setInspectorOpen(!inspectorOpen)}
              >
                {inspectorOpen ? "Hide" : "Show"}
              </Button>
            </div>

            {inspectorOpen && (
              <>
                {/* Agent selector */}
                <Card className="gap-6 py-6 shadow-sm">
                  <CardHeader className="space-y-1 px-6">
                    <CardTitle className="text-lg">Agent</CardTitle>
                    <CardDescription className="text-[13px] leading-relaxed">
                      Choose which workspace agent receives this thread.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3 px-6">
                    <Label htmlFor="agent-pick">Active agent</Label>
                    <Select value={agentId} onValueChange={(v) => v != null && onSelectAgent(v)}>
                      <SelectTrigger id="agent-pick" className="h-10 w-full min-w-0 max-w-full" size="default">
                        <SelectValue>{activeAgentLabel}</SelectValue>
                      </SelectTrigger>
                      <SelectContent>
                        {agents.map((a) => (
                          <SelectItem key={a.id} value={a.id}>
                            {agentDisplayName(a)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <div className="space-y-2 pt-2">
                      <Label htmlFor="agent-rename">Display name</Label>
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                        <Input
                          id="agent-rename"
                          value={agentRenameDraft}
                          onChange={(e) => setAgentRenameDraft(e.target.value)}
                          placeholder="Name shown in lists"
                          className="text-sm"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={savingName || !agentRenameDraft.trim()}
                          onClick={() => void saveAgentDisplayName()}
                        >
                          {savingName ? "Saving…" : "Save name"}
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Recent runs timeline */}
                <Card className="gap-6 py-6 shadow-sm">
                  <CardHeader className="space-y-1 px-6">
                    <CardTitle className="text-lg">Recent runs</CardTitle>
                    <CardDescription className="text-[13px] leading-relaxed">
                      Latest executions in this workspace.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="px-6">
                    <AgentTimeline
                      executions={executions.slice(0, 12)}
                      activeId={activeExecutionId}
                    />
                  </CardContent>
                </Card>

                {/* Capabilities */}
                <Card className="gap-6 py-6 shadow-sm">
                  <CardHeader className="space-y-1 px-6">
                    <CardTitle className="text-lg">Capabilities</CardTitle>
                    <CardDescription className="text-[13px] leading-relaxed">
                      Switches update this agent&apos;s saved configuration. Remember to save before running.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-5 px-6">
                    {TOOL_ROWS.map(({ key, title, desc }, i) => (
                      <div key={key}>
                        {i > 0 ? <Separator className="mb-5" /> : null}
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0 space-y-1">
                            <span className="block text-sm font-medium leading-snug">{title}</span>
                            <span className="text-muted-foreground text-xs leading-relaxed">{desc}</span>
                          </div>
                          <Switch
                            checked={tools[key]}
                            onCheckedChange={(checked) => {
                              setTools((t) => ({ ...t, [key]: checked }));
                              setToolsSaved(false);
                            }}
                            aria-label={title}
                            className="shrink-0"
                          />
                        </div>
                      </div>
                    ))}
                    <Separator />
                    <Button type="button" variant="secondary" disabled={savingTools} onClick={() => void saveTools()}>
                      {savingTools ? "Saving…" : "Save capabilities"}
                      {toolsSaved ? <Check className="ml-2 h-3.5 w-3.5" /> : null}
                    </Button>
                  </CardContent>
                </Card>
              </>
            )}
          </aside>
        </div>
      </div>
    </>
  );
}
