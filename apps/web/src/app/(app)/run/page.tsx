"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowUp,
  Bot,
  ChevronDown,
  Loader2,
  Sparkles,
  Settings2,
  User,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
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

type AgentRow = { id: string; name: string; template: string; config: Record<string, unknown> };

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
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
};

const SUGGESTIONS = [
  { text: "Summarize the latest AI agent frameworks", icon: "🤖" },
  { text: "Compare RAG vs fine-tuning tradeoffs", icon: "⚡" },
  { text: "What are JEPA architectures?", icon: "🧠" },
];

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
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [citations, setCitations] = useState<CitationSource[]>([]);
  const [showInspector, setShowInspector] = useState(true);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const activeAgent = useMemo(() => agents.find((a) => a.id === agentId), [agents, agentId]);
  const hasConversation = messages.length > 0;

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    apiFetch<{ workspaces: { id: string }[] }>("/api/v1/auth/me")
      .then((m) => {
        const w = m.workspaces[0];
        if (!w) return;
        setWsId(w.id);
        return apiFetch<{ agents: AgentRow[] }>(`/api/v1/workspaces/${w.id}/agents`);
      })
      .then((a) => {
        if (!a?.agents?.length) return;
        setAgents(a.agents);
        setAgentId(a.agents[0].id);
      })
      .finally(() => setBootDone(true));
  }, [router]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const run = useCallback(async () => {
    if (!agentId || !message.trim() || running) return;
    const userMsg = message.trim();
    setRunning(true);
    setMessage("");
    reset();
    setToolCalls([]);
    setCitations([]);

    // Add user message
    setMessages((prev) => [...prev, { role: "user", content: userMsg, timestamp: new Date() }]);

    try {
      const res = await apiFetch<{ execution_id: string }>(`/api/v1/agents/${agentId}/execute`, {
        method: "POST",
        json: { message: userMsg },
      });
      const eid = res.execution_id;
      setActiveExecution(eid);
      setNode("planner", { status: "thinking" });
      track("run_started", { agent_id: agentId, execution_id: eid });

      const { stream_jwt } = await apiFetch<{ stream_jwt: string }>(
        `/api/v1/executions/${eid}/stream-token`,
        { method: "POST" },
      );
      const url = `${getApiBase()}/api/v1/executions/${eid}/stream?stream_jwt=${encodeURIComponent(stream_jwt)}`;
      const es = new EventSource(url);

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
          } else if (data.kind === "final" && data.answer) {
            appendToken(data.answer);
            setNode("synthesizer", { status: "done" });
            // Add assistant message
            setMessages((prev) => [
              ...prev,
              { role: "assistant", content: String(data.answer), timestamp: new Date() },
            ]);
          } else if (data.kind === "error") {
            setNode("synthesizer", { status: "error" });
            setMessages((prev) => [
              ...prev,
              { role: "assistant", content: `Error: ${data.message || "Execution failed"}`, timestamp: new Date() },
            ]);
          } else if (data.kind === "done") {
            es.close();
            setRunning(false);
            setActiveExecution(null);
            track("run_completed", { execution_id: eid, agent_id: agentId });
          }
        } catch { /* non-JSON frame */ }
      };

      es.onerror = () => {
        es.close();
        setRunning(false);
        setActiveExecution(null);
        setNode("synthesizer", { status: "error" });
      };
    } catch {
      setRunning(false);
      setActiveExecution(null);
      track("run_failed", { agent_id: agentId });
    }
  }, [agentId, message, running, reset, setNode, appendToken, setActiveExecution]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void run();
    }
  }, [run]);

  if (!bootDone) {
    return (
      <div className="flex h-[calc(100vh-48px)] items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-48px)] flex-col">
      {/* Main area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Chat column */}
        <div className="flex flex-1 flex-col">
          {/* Messages area */}
          <div className="flex-1 overflow-y-auto">
            {!hasConversation && !running ? (
              /* Empty state */
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

                  {/* Suggestions as cards */}
                  <div className="grid w-full gap-3 sm:grid-cols-3">
                    {SUGGESTIONS.map((q) => (
                      <button
                        key={q.text}
                        onClick={() => { setMessage(q.text); textareaRef.current?.focus(); }}
                        className={cn(
                          "surface-glass group flex flex-col gap-3 rounded-2xl p-5 text-left transition-all duration-300",
                          "hover:-translate-y-1 hover:border-flow-brand/40 hover:shadow-lg hover:shadow-flow-brand/10"
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
              /* Conversation */
              <div className="mx-auto w-full max-w-3xl px-4 py-6 space-y-4">
                {messages.map((msg, i) => (
                  <div
                    key={i}
                    className={cn(
                      "flex gap-3 animate-slide-up",
                      msg.role === "user" ? "justify-end" : "justify-start",
                    )}
                    style={{ animationDelay: `${i * 30}ms` }}
                  >
                    {msg.role === "assistant" && (
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border/60 bg-card">
                        <Bot className="h-4 w-4 text-flow-brand" />
                      </div>
                    )}
                    <div
                      className={cn(
                        "max-w-[80%] rounded-2xl px-5 py-3.5 text-sm leading-relaxed",
                        msg.role === "user"
                          ? "rounded-br-md bg-flow-brand text-white shadow-md shadow-flow-brand/20"
                          : "surface-glass rounded-bl-md text-foreground shadow-sm",
                      )}
                    >
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                    {msg.role === "user" && (
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                        <User className="h-4 w-4 text-muted-foreground" />
                      </div>
                    )}
                  </div>
                ))}

                {running && (
                  <div className="flex gap-3 animate-slide-up">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-flow-streaming/30 bg-card shadow-[0_0_12px_rgba(var(--color-flow-streaming),0.25)]">
                      <Bot className="h-4 w-4 text-flow-streaming animate-pulse" />
                    </div>
                    <div className="surface-glass max-w-[80%] rounded-2xl rounded-bl-md px-5 py-3.5 shadow-sm">
                      <TokenStream placeholder="Thinking…" />
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            )}
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
                  <SelectTrigger
                    className="h-9 w-auto min-w-[160px] max-w-[200px] shrink-0 gap-1.5 rounded-xl border-border/60 bg-muted/40 text-xs"
                  >
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
                  placeholder="Ask anything…"
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

              {/* Settings + Inspector toggle */}
              <div className="flex shrink-0 gap-1">
                <button
                  onClick={() => setShowInspector(!showInspector)}
                  className={cn(
                    "rounded-lg p-2 transition-colors",
                    showInspector
                      ? "text-flow-brand bg-flow-brand/10"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                  title="Toggle inspector"
                >
                  <Sparkles className="h-4 w-4" />
                </button>
                <button
                  onClick={() => router.push("/settings")}
                  className="rounded-lg p-2 text-muted-foreground hover:text-foreground transition-colors"
                  title="Settings"
                >
                  <Settings2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Inspector sidebar */}
        <div 
          className={cn(
            "absolute right-0 top-0 h-full w-full sm:w-[400px] border-l border-border/40 bg-background/95 backdrop-blur-md lg:static lg:bg-transparent lg:w-[400px] xl:w-[450px]",
            "transition-transform duration-300 z-50 p-3",
            showInspector && hasConversation ? "translate-x-0" : "translate-x-full lg:hidden"
          )}
        >
          {hasConversation && (
            <RunInspector toolCalls={toolCalls} citations={citations} className="h-full w-full shadow-none border-0 lg:surface-glass-heavy lg:rounded-2xl lg:shadow-xl" />
          )}
        </div>
      </div>
    </div>
  );
}
