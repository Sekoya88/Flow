"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowUp,
  Bot,
  CheckCircle2,
  Clock,
  Loader2,
  MessageSquarePlus,
  Sparkles,
  Target,
  User,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RunInspector } from "@/components/flow/RunInspector";
import { TokenStream } from "@/components/flow/TokenStream";
import { FlowMarkAnimated } from "@/components/brand/FlowLogo";
import { ApiError, apiFetch, getApiBase } from "@/lib/api";
import { track } from "@/lib/analytics";
import { getToken } from "@/lib/auth";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { ToolCall } from "@/components/flow/ToolCallLog";
import type { CitationSource } from "@/components/flow/CitationsPanel";
import { SubagentCard, type SubagentInvocation } from "@/components/flow/SubagentCard";

type AgentRow = { id: string; name: string; template: string; config: Record<string, unknown> };

type ExecutionRow = {
  id: string;
  status: string;
  agent_id: string;
  agent_name: string;
  user_message: string;
  answer: string | null;
  thread_id: string;
  created_at: string | null;
  completed_at: string | null;
};

type ThreadTurn = {
  id: string;
  status: string;
  user_message: string;
  answer: string | null;
  created_at: string | null;
};

type SseEvent = {
  kind: string;
  node?: string;
  summary?: string;
  answer?: string;
  text?: string;
  message?: string;
  confidence?: number;
  tool?: string;
  input?: Record<string, unknown>;
  output?: string;
  duration_ms?: number;
  status?: string;
  payload?: unknown;
  agent_name?: string;
};

const SUGGESTIONS = [
  { text: "Summarize the latest AI agent frameworks", icon: "🤖" },
  { text: "Compare RAG vs fine-tuning tradeoffs", icon: "⚡" },
  { text: "What are JEPA architectures?", icon: "🧠" },
];

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

function groupByDate(execs: ExecutionRow[]): { label: string; items: ExecutionRow[] }[] {
  const groups: Record<string, ExecutionRow[]> = {};
  for (const e of execs) {
    const d = e.created_at ? new Date(e.created_at) : new Date();
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    let label: string;
    if (diff < 86400000) label = "Today";
    else if (diff < 172800000) label = "Yesterday";
    else if (diff < 604800000) label = "This week";
    else label = d.toLocaleDateString("en-US", { month: "long", year: "numeric" });
    if (!groups[label]) groups[label] = [];
    groups[label].push(e);
  }
  const order = ["Today", "Yesterday", "This week"];
  const keys = Object.keys(groups).sort((a, b) => {
    const ai = order.indexOf(a);
    const bi = order.indexOf(b);
    if (ai !== -1 && bi !== -1) return ai - bi;
    if (ai !== -1) return -1;
    if (bi !== -1) return 1;
    return 0;
  });
  return keys.map((label) => ({ label, items: groups[label] }));
}

export default function RunPage() {
  const router = useRouter();
  const setNode = useStore((s) => s.setNode);
  const appendToken = useStore((s) => s.appendToken);
  const reset = useStore((s) => s.reset);
  const setActiveExecution = useStore((s) => s.setActiveExecution);

  const [wsId, setWsId] = useState<string | null>(null);
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [agentId, setAgentId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [running, setRunning] = useState(false);
  const [bootDone, setBootDone] = useState(false);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [citations, setCitations] = useState<CitationSource[]>([]);
  const [showInspector, setShowInspector] = useState(false);
  const [goldenSetId, setGoldenSetId] = useState<string | null>(null);
  const [markedItems, setMarkedItems] = useState<Set<string>>(new Set());
  const [markingId, setMarkingId] = useState<string | null>(null);

  // History
  const [history, setHistory] = useState<ExecutionRow[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [liveAnswer, setLiveAnswer] = useState<string | null>(null);
  const [threadTurns, setThreadTurns] = useState<ThreadTurn[]>([]);
  const [threadLoading, setThreadLoading] = useState(false);

  // Onboarding completion banner
  const [onboardingDone, setOnboardingDone] = useState<boolean | null>(null);

  // Subagent invocations during the active run, keyed by agentName + start order
  const [subagentInvocations, setSubagentInvocations] = useState<SubagentInvocation[]>([]);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const selectedExec = useMemo(
    () => history.find((e) => e.id === selectedId) ?? null,
    [history, selectedId],
  );
  const grouped = useMemo(() => groupByDate(history), [history]);
  const isNewChat = selectedId === null;

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    setHistoryLoading(true);
    apiFetch<{ workspaces: { id: string }[] }>("/api/v1/auth/me")
      .then((m) => {
        const w = m.workspaces[0];
        if (!w) return;
        setWsId(w.id);
        apiFetch<{ completed: boolean }>(`/api/v1/preferences/onboarding-status?workspace_id=${w.id}`)
          .then((s) => setOnboardingDone(s.completed))
          .catch(() => setOnboardingDone(false));
        return apiFetch<{ agents: AgentRow[] }>(`/api/v1/workspaces/${w.id}/agents`);
      })
      .then(async (a) => {
        if (a?.agents?.length) {
          setAgents(a.agents);
          setAgentId(a.agents[0].id);
        }
        try {
          const setsData = await apiFetch<{ sets: { id: string }[] }>("/api/v1/golden-sets");
          if (setsData.sets?.length) setGoldenSetId(setsData.sets[0].id);
        } catch { /* ignore */ }
      })
      .catch(() => {})
      .finally(() => setBootDone(true));

    apiFetch<{ executions: ExecutionRow[] }>("/api/v1/executions")
      .then((r) => setHistory(r.executions))
      .catch(() => {})
      .finally(() => setHistoryLoading(false));
  }, [router]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [selectedExec, liveAnswer, running]);

  const refreshHistory = useCallback(() => {
    apiFetch<{ executions: ExecutionRow[] }>("/api/v1/executions")
      .then((r) => setHistory(r.executions))
      .catch(() => {});
  }, []);

  const startNewChat = useCallback(() => {
    setSelectedId(null);
    setLiveAnswer(null);
    setThreadTurns([]);
    reset();
    setToolCalls([]);
    setCitations([]);
    setSubagentInvocations([]);
    textareaRef.current?.focus();
  }, [reset]);

  // Load all turns when a thread is selected
  useEffect(() => {
    if (!selectedExec) {
      setThreadTurns([]);
      return;
    }
    setThreadLoading(true);
    apiFetch<{ executions: ThreadTurn[] }>(`/api/v1/executions/threads/${selectedExec.thread_id}`)
      .then((r) => setThreadTurns(r.executions))
      .catch(() => setThreadTurns([]))
      .finally(() => setThreadLoading(false));
  }, [selectedExec]);

  const run = useCallback(async () => {
    if (!agentId || !message.trim() || running) return;
    const userMsg = message.trim();
    setRunning(true);
    setMessage("");
    setLiveAnswer(null);
    reset();
    setToolCalls([]);
    setCitations([]);
    setSubagentInvocations([]);

    // If we're continuing a selected thread, send parent_execution_id
    const parentId =
      selectedId && selectedId !== "pending" && history.find((e) => e.id === selectedId)
        ? selectedId
        : null;
    const continuingThreadId = parentId
      ? history.find((e) => e.id === parentId)?.thread_id ?? null
      : null;

    // Optimistic entry in history
    const optimisticId = "pending";
    const optimistic: ExecutionRow = {
      id: optimisticId,
      status: "running",
      agent_id: agentId,
      agent_name: agents.find((a) => a.id === agentId)?.name || "Agent",
      user_message: userMsg,
      answer: null,
      thread_id: continuingThreadId ?? optimisticId,
      created_at: new Date().toISOString(),
      completed_at: null,
    };
    setHistory((prev) => [optimistic, ...prev]);
    setSelectedId(optimisticId);
    if (continuingThreadId) {
      setThreadTurns((prev) => [
        ...prev,
        {
          id: optimisticId,
          status: "running",
          user_message: userMsg,
          answer: null,
          created_at: optimistic.created_at,
        },
      ]);
    } else {
      setThreadTurns([]);
    }

    try {
      const res = await apiFetch<{ execution_id: string; thread_id: string }>(
        `/api/v1/agents/${agentId}/execute`,
        {
          method: "POST",
          json: parentId
            ? { message: userMsg, parent_execution_id: parentId }
            : { message: userMsg },
        },
      );
      const eid = res.execution_id;
      const tid = res.thread_id;
      // Replace optimistic entry
      setHistory((prev) =>
        prev.map((e) => (e.id === optimisticId ? { ...e, id: eid, thread_id: tid } : e)),
      );
      setThreadTurns((prev) =>
        prev.map((t) => (t.id === optimisticId ? { ...t, id: eid } : t)),
      );
      setSelectedId(eid);
      setActiveExecution(eid);
      setNode("planner", { status: "thinking" });
      track("run_started", { agent_id: agentId, execution_id: eid });

      const { stream_jwt } = await apiFetch<{ stream_jwt: string }>(
        `/api/v1/executions/${eid}/stream-token`,
        { method: "POST" },
      );
      const url = `${getApiBase()}/api/v1/executions/${eid}/stream?stream_jwt=${encodeURIComponent(stream_jwt)}`;
      const es = new EventSource(url);
      let fullAnswer = "";

      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as SseEvent;
          if (data.kind === "node_update" && data.node) {
            const order = ["planner", "worker", "synthesizer", "reflector"];
            const idx = order.indexOf(data.node);
            if (idx > 0) setNode(order[idx - 1], { status: "done" });
            setNode(data.node, { status: "streaming" });
          } else if (data.kind === "token" && data.text) {
            appendToken(data.text);
            fullAnswer += data.text;
            setLiveAnswer(fullAnswer);
          } else if (data.kind === "tool_call" && data.tool) {
            setToolCalls((prev) => [
              ...prev,
              {
                id: `tc-${prev.length}`,
                tool: data.tool!,
                input: data.input ?? {},
                output: data.output ?? "",
                duration_ms: data.duration_ms ?? 0,
                status: (data.status as "success" | "error") ?? "success",
              },
            ]);
          } else if (data.kind === "citations" && data.payload) {
            setCitations(data.payload as CitationSource[]);
          } else if (data.kind === "subagent_start" && data.agent_name) {
            const agentName = data.agent_name!;
            setSubagentInvocations((prev) => [
              ...prev,
              {
                key: `${agentName}-${prev.length}-${Date.now()}`,
                agentName,
                message: data.message ?? "",
                status: "running",
              },
            ]);
          } else if (data.kind === "subagent_done" && data.agent_name) {
            const agentName = data.agent_name!;
            setSubagentInvocations((prev) => {
              // Resolve the most recent matching "running" invocation
              const idx = [...prev]
                .map((inv, i) => ({ inv, i }))
                .reverse()
                .find((x) => x.inv.agentName === agentName && x.inv.status === "running")?.i;
              if (idx === undefined) return prev;
              const next = [...prev];
              next[idx] = {
                ...next[idx],
                status: data.status === "error" ? "error" : "success",
                answer: data.answer ?? null,
                durationMs: data.duration_ms ?? null,
              };
              return next;
            });
          } else if (data.kind === "final" && data.answer) {
            fullAnswer = String(data.answer);
            setLiveAnswer(fullAnswer);
            setNode("synthesizer", { status: "done" });
            setHistory((prev) =>
              prev.map((e) =>
                e.id === eid ? { ...e, status: "completed", answer: fullAnswer, completed_at: new Date().toISOString() } : e,
              ),
            );
            setThreadTurns((prev) =>
              prev.map((t) =>
                t.id === eid ? { ...t, status: "completed", answer: fullAnswer } : t,
              ),
            );
          } else if (data.kind === "error") {
            setNode("synthesizer", { status: "error" });
            setHistory((prev) =>
              prev.map((e) =>
                e.id === eid ? { ...e, status: "failed", answer: `Error: ${data.message || "Execution failed"}`, completed_at: new Date().toISOString() } : e,
              ),
            );
          } else if (data.kind === "done") {
            es.close();
            setRunning(false);
            setActiveExecution(null);
            track("run_completed", { execution_id: eid, agent_id: agentId });
            refreshHistory();
          }
        } catch { /* non-JSON frame */ }
      };

      es.onerror = () => {
        es.close();
        setRunning(false);
        setActiveExecution(null);
        setNode("synthesizer", { status: "error" });
        refreshHistory();
      };
    } catch {
      setRunning(false);
      setActiveExecution(null);
      setHistory((prev) => prev.filter((e) => e.id !== optimisticId));
      track("run_failed", { agent_id: agentId });
    }
  }, [agentId, agents, message, running, reset, setNode, appendToken, setActiveExecution, refreshHistory]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void run();
    }
  }, [run]);

  const handleMarkAsGolden = useCallback(async (execId: string, userMsg: string, answer: string) => {
    if (!goldenSetId) return;
    setMarkingId(execId);
    try {
      await apiFetch(`/api/v1/golden-sets/${goldenSetId}/items`, {
        method: "POST",
        json: {
          input_text: userMsg,
          expected_output: answer,
          scoring_criteria: "Generated from chat",
        },
      });
      setMarkedItems((prev) => new Set(prev).add(execId));
    } catch {
      // ignore
    } finally {
      setMarkingId(null);
    }
  }, [goldenSetId]);

  if (!bootDone) {
    return (
      <div className="flex h-[calc(100vh-48px)] items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const isRunningSelected = running && selectedId !== null && history.some((e) => e.id === selectedId && e.status === "running");

  return (
    <div className="flex h-[calc(100vh-48px)]">
      {/* Left sidebar — history */}
      <aside className="hidden md:flex w-64 shrink-0 flex-col border-r border-border/40 bg-muted/20">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border/40">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">History</span>
          <button
            onClick={startNewChat}
            className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            title="New chat"
          >
            <MessageSquarePlus className="h-3.5 w-3.5" />
            New
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-2">
          {historyLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          )}
          {!historyLoading && history.length === 0 && (
            <p className="px-4 py-6 text-xs text-muted-foreground text-center">No runs yet. Ask something!</p>
          )}
          {grouped.map(({ label, items }) => (
            <div key={label} className="mb-2">
              <p className="px-4 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                {label}
              </p>
              {items.map((exec) => (
                <button
                  key={exec.id}
                  onClick={() => {
                    setSelectedId(exec.id);
                    if (exec.answer) setLiveAnswer(null);
                  }}
                  className={cn(
                    "w-full px-4 py-2.5 text-left transition-colors group",
                    selectedId === exec.id
                      ? "bg-flow-brand/10 border-r-2 border-flow-brand"
                      : "hover:bg-muted/60",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className={cn(
                      "text-xs font-medium line-clamp-2 leading-relaxed",
                      selectedId === exec.id ? "text-foreground" : "text-foreground/80",
                    )}>
                      {exec.user_message}
                    </p>
                    {exec.status === "running" && (
                      <Zap className="h-3 w-3 shrink-0 text-flow-streaming animate-pulse mt-0.5" />
                    )}
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="text-[10px] text-muted-foreground/60 truncate max-w-[100px]">
                      {exec.agent_name}
                    </span>
                    <span className="text-[10px] text-muted-foreground/40">·</span>
                    <span className="text-[10px] text-muted-foreground/60">
                      {timeAgo(exec.created_at)}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          ))}
        </div>

        {/* Sidebar footer — profile / onboarding access */}
        <div className="border-t border-border/40 px-3 py-3 space-y-2">
          {onboardingDone === false && (
            <button
              onClick={() => router.push("/onboarding/profile")}
              className="w-full flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium bg-flow-brand/15 text-flow-brand border border-flow-brand/30 hover:bg-flow-brand/25 transition-colors"
            >
              <Sparkles className="h-3.5 w-3.5" />
              Finish onboarding
            </button>
          )}
          <button
            onClick={() => router.push("/settings/profile")}
            className="w-full flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <User className="h-3.5 w-3.5" />
            Profile & preferences
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Messages area */}
        <div className="flex flex-1 overflow-hidden">
          <div className="flex flex-1 flex-col overflow-y-auto">
            {isNewChat && !running ? (
              /* Empty / new chat state */
              <div className="flex h-full w-full flex-col items-center justify-center px-4">
                <div className="flex w-full max-w-xl flex-col items-center gap-8 animate-fade-in">
                  <div className="flex flex-col items-center gap-4 text-center">
                    <FlowMarkAnimated className="text-flow-brand opacity-80" />
                    <div className="space-y-2">
                      <h1 className="text-2xl font-semibold tracking-tight">
                        What do you want to explore?
                      </h1>
                      <p className="text-sm text-muted-foreground max-w-md leading-relaxed">
                        Your agent will plan, research, and synthesize an answer.
                        Results feed into the knowledge graph.
                      </p>
                    </div>
                  </div>
                  <div className="grid w-full gap-3 sm:grid-cols-3">
                    {SUGGESTIONS.map((q) => (
                      <button
                        key={q.text}
                        onClick={() => { setMessage(q.text); textareaRef.current?.focus(); }}
                        className={cn(
                          "surface-glass group flex flex-col gap-3 rounded-2xl p-5 text-left transition-all duration-300",
                          "hover:-translate-y-1 hover:border-flow-brand/40 hover:shadow-lg hover:shadow-flow-brand/10",
                        )}
                      >
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-flow-brand/10 text-xl">
                          {q.icon}
                        </div>
                        <span className="text-sm font-medium text-foreground/80 transition-colors group-hover:text-foreground leading-relaxed">
                          {q.text}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              /* Conversation view — multi-turn thread */
              <div className="mx-auto w-full max-w-3xl px-4 py-6 space-y-6">
                {threadLoading && threadTurns.length === 0 && (
                  <div className="flex justify-center py-8">
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  </div>
                )}
                {(threadTurns.length > 0 ? threadTurns : selectedExec ? [{
                  id: selectedExec.id,
                  status: selectedExec.status,
                  user_message: selectedExec.user_message,
                  answer: selectedExec.answer,
                  created_at: selectedExec.created_at,
                }] : []).map((turn, idx, arr) => {
                  const isLastTurn = idx === arr.length - 1;
                  const isStreamingTurn = isLastTurn && running && turn.id === selectedId;
                  const displayAnswer = isStreamingTurn ? (liveAnswer ?? turn.answer) : turn.answer;
                  return (
                    <div key={turn.id} className="space-y-4">
                      {/* User message */}
                      <div className="flex gap-3 justify-end animate-slide-up">
                        <div className="flex flex-col gap-1.5 max-w-[80%]">
                          <div className="rounded-2xl rounded-br-md bg-flow-brand px-5 py-3.5 text-sm leading-relaxed text-white shadow-md shadow-flow-brand/20">
                            <p className="whitespace-pre-wrap">{turn.user_message}</p>
                          </div>
                          {turn.created_at && (
                            <div className="flex items-center justify-end gap-1.5 pr-1">
                              <Clock className="h-3 w-3 text-muted-foreground/40" />
                              <span className="text-[10px] text-muted-foreground/50">
                                {timeAgo(turn.created_at)}
                              </span>
                            </div>
                          )}
                        </div>
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                          <User className="h-4 w-4 text-muted-foreground" />
                        </div>
                      </div>

                      {/* Subagent invocations (only on the last/streaming turn) */}
                      {isLastTurn && subagentInvocations.length > 0 && (
                        <div className="ml-11 space-y-2 animate-fade-in">
                          {subagentInvocations.map((inv) => (
                            <SubagentCard key={inv.key} invocation={inv} />
                          ))}
                        </div>
                      )}

                      {/* Agent response */}
                      {(displayAnswer || isStreamingTurn) && (
                        <div className="flex gap-3 animate-slide-up">
                          <div className={cn(
                            "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border/60 bg-card",
                            isStreamingTurn && "border-flow-streaming/30 shadow-[0_0_12px_rgba(var(--color-flow-streaming),0.25)]",
                          )}>
                            <Bot className={cn(
                              "h-4 w-4",
                              isStreamingTurn ? "text-flow-streaming animate-pulse" : "text-flow-brand",
                            )} />
                          </div>
                          <div className="flex flex-col gap-1.5 max-w-[80%]">
                            <div className="surface-glass rounded-2xl rounded-bl-md px-5 py-3.5 shadow-sm text-sm leading-relaxed text-foreground">
                              {isStreamingTurn && !displayAnswer ? (
                                <TokenStream placeholder="Thinking…" />
                              ) : (
                                <p className="whitespace-pre-wrap">{displayAnswer}</p>
                              )}
                            </div>
                            {turn.answer && goldenSetId && (
                              <div className="flex justify-start pl-1">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className={cn(
                                    "h-6 px-2 text-[10px] uppercase tracking-wider font-semibold transition-colors gap-1",
                                    markedItems.has(turn.id)
                                      ? "text-green-500 hover:text-green-600 bg-green-500/10 hover:bg-green-500/20"
                                      : "text-muted-foreground/50 hover:text-flow-brand hover:bg-flow-brand/10",
                                  )}
                                  disabled={markedItems.has(turn.id) || markingId === turn.id}
                                  onClick={() => void handleMarkAsGolden(turn.id, turn.user_message, turn.answer!)}
                                >
                                  {markingId === turn.id ? (
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                  ) : markedItems.has(turn.id) ? (
                                    <CheckCircle2 className="h-3 w-3" />
                                  ) : (
                                    <Target className="h-3 w-3" />
                                  )}
                                  {markedItems.has(turn.id) ? "Added to Golden" : "Mark as Golden"}
                                </Button>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}

                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Inspector sidebar */}
          <div
            className={cn(
              "absolute right-0 top-0 h-full w-full sm:w-[400px] border-l border-border/40 bg-background/95 backdrop-blur-md lg:static lg:bg-transparent lg:w-[400px] xl:w-[450px]",
              "transition-transform duration-300 z-50 p-3",
              showInspector && (isRunningSelected || (selectedExec && (toolCalls.length > 0 || citations.length > 0)))
                ? "translate-x-0"
                : "translate-x-full lg:hidden",
            )}
          >
            <RunInspector
              toolCalls={toolCalls}
              citations={citations}
              className="h-full w-full shadow-none border-0 lg:surface-glass-heavy lg:rounded-2xl lg:shadow-xl"
            />
          </div>
        </div>

        {/* Bottom input bar */}
        <div className="border-t border-border/40 bg-background/80 backdrop-blur-md px-4 py-3">
          <div className="mx-auto flex w-full max-w-3xl items-end gap-3">
            {/* Agent selector */}
            {agents.length > 0 && (
              <Select
                value={agentId ?? undefined}
                onValueChange={(v) => { if (v) setAgentId(v); }}
              >
                <SelectTrigger className="h-9 w-auto min-w-[160px] max-w-[200px] shrink-0 gap-1.5 rounded-xl border-border/60 bg-muted/40 text-xs">
                  <Bot className="h-3.5 w-3.5 text-muted-foreground" />
                  <SelectValue placeholder="Agent" />
                </SelectTrigger>
                <SelectContent>
                  {agents.map((a) => (
                    <SelectItem key={a.id} value={a.id}>
                      {a.name || a.template}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {/* Textarea */}
            <div className="relative flex-1">
              <textarea
                ref={textareaRef}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={selectedExec?.answer ? "Ask a follow-up…" : "Ask anything…"}
                rows={1}
                className={cn(
                  "w-full resize-none rounded-xl border border-border/60 bg-card/80 px-4 py-3 pr-12",
                  "text-sm leading-relaxed placeholder:text-muted-foreground/60",
                  "focus:outline-none focus:ring-2 focus:ring-flow-brand/30 focus:border-flow-brand/50",
                  "transition-all min-h-[44px] max-h-[160px]",
                )}
                style={{ height: "auto", overflow: "hidden" }}
                onInput={(e) => {
                  const t = e.currentTarget;
                  t.style.height = "auto";
                  t.style.height = `${Math.min(t.scrollHeight, 160)}px`;
                }}
              />
              <Button
                size="icon"
                onClick={() => void run()}
                disabled={running || !message.trim()}
                className={cn(
                  "absolute right-2 bottom-2 h-8 w-8 rounded-lg transition-all",
                  message.trim() && !running
                    ? "bg-flow-brand text-white hover:bg-flow-brand/90 shadow-md shadow-flow-brand/20"
                    : "bg-muted text-muted-foreground",
                )}
              >
                {running ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ArrowUp className="h-4 w-4" />
                )}
              </Button>
            </div>

            {/* Inspector toggle */}
            <button
              onClick={() => setShowInspector(!showInspector)}
              className={cn(
                "rounded-lg p-2 transition-colors shrink-0",
                showInspector
                  ? "text-flow-brand bg-flow-brand/10"
                  : "text-muted-foreground hover:text-foreground",
              )}
              title="Toggle inspector"
            >
              <Sparkles className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
