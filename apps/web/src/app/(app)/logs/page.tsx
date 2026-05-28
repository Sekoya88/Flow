"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  Bot,
  BookOpen,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Code2,
  ExternalLink,
  Gauge,
  MessageSquare,
  Radio,
  Sparkles,
  Terminal,
  TrendingUp,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { logger } from "@/lib/logger";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────

type ObsStatus = {
  langsmith_enabled: boolean;
  project: string | null;
  trace_url: string | null;
  log_level: string;
  log_json: boolean;
};

type ExecutionRow = {
  id: string;
  agent_id: string;
  agent_name: string;
  agent_template: string;
  status: "running" | "completed" | "failed";
  error: string | null;
  user_message: string;
  answer: string;
  created_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  node_count: number;
  tool_count: number;
  llm_count: number;
  total_tokens: number | null;
};

type TimelineEvent = {
  id: number;
  kind: string;
  created_at: string;
  payload: Record<string, unknown>;
  node?: string;
  tool?: string;
  duration_ms?: number;
  status?: string;
  model?: string;
  latency_ms?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  answer?: string;
  confidence?: number;
  message?: string;
};

type SkillUsed = {
  skill_id: string;
  skill_name: string;
  matched_text: string | null;
  created_at: string;
};

type LogDetail = {
  id: string;
  agent_name: string;
  status: string;
  error: string | null;
  user_message: string;
  created_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  timeline: TimelineEvent[];
  skills_used: SkillUsed[];
};

// ── Helpers ───────────────────────────────────────────────────────────

function fmtDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function fmtTokens(n: number | null): string {
  if (n === null) return "";
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k tok`;
  return `${n} tok`;
}

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

// ── Event kind config ─────────────────────────────────────────────────

const EVENT_KINDS: Record<string, { icon: React.FC<{ className?: string }>; color: string; label: string }> = {
  node_update:    { icon: Zap,           color: "text-blue-400",     label: "Node" },
  tool_call:      { icon: Code2,          color: "text-amber-400",    label: "Tool" },
  "llm.start":    { icon: Radio,          color: "text-violet-400",   label: "LLM" },
  llm_start:      { icon: Radio,          color: "text-violet-400",   label: "LLM" },
  "llm.end":      { icon: Radio,          color: "text-violet-300",   label: "LLM" },
  llm_end:        { icon: Radio,          color: "text-violet-300",   label: "LLM" },
  final:          { icon: CheckCircle2,   color: "text-emerald-400",  label: "Final" },
  error:          { icon: AlertTriangle,  color: "text-red-400",      label: "Error" },
  token:          { icon: Terminal,       color: "text-muted-foreground", label: "Token" },
  citations:      { icon: MessageSquare,  color: "text-sky-400",      label: "Citations" },
  skill_invoked:  { icon: Sparkles,       color: "text-flow-violet",  label: "Skill" },
};

// ── Status badge ──────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const cfg = {
    completed: { variant: "default" as const, label: "completed", cls: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" },
    failed:    { variant: "destructive" as const, label: "failed",    cls: "" },
    running:   { variant: "secondary" as const, label: "running",   cls: "border-amber-500/30 bg-amber-500/10 text-amber-400" },
  }[status] ?? { variant: "outline" as const, label: status, cls: "" };
  return (
    <Badge variant="outline" className={cn("capitalize text-[10px] px-1.5 h-5", cfg.cls)}>
      {cfg.label}
    </Badge>
  );
}

// ── Timeline event row ────────────────────────────────────────────────

function EventRow({ ev }: { ev: TimelineEvent }) {
  const cfg = EVENT_KINDS[ev.kind] ?? { icon: Terminal, color: "text-muted-foreground", label: ev.kind };
  const Icon = cfg.icon;

  // Skip noisy token events
  if (ev.kind === "token") return null;

  let detail = "";
  if (ev.node) detail = ev.node;
  else if (ev.tool) detail = `${ev.tool}${ev.duration_ms ? ` · ${ev.duration_ms}ms` : ""}`;
  else if (ev.model) detail = ev.model;
  else if (ev.latency_ms) detail = `${ev.latency_ms}ms`;
  else if (ev.answer) detail = ev.answer.slice(0, 120);
  else if (ev.message) detail = ev.message;

  const ts = new Date(ev.created_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit", fractionalSecondDigits: 1 });

  return (
    <div className="flex items-start gap-2.5 py-1.5 px-3 group hover:bg-muted/20 rounded transition-colors">
      <span className="text-[10px] text-muted-foreground/50 font-mono pt-0.5 shrink-0 w-[68px]">{ts}</span>
      <Icon className={cn("h-3.5 w-3.5 shrink-0 mt-0.5", cfg.color)} />
      <div className="flex items-baseline gap-2 min-w-0">
        <span className={cn("text-[11px] font-semibold shrink-0", cfg.color)}>{cfg.label}</span>
        {detail && <span className="text-[11px] text-foreground/70 truncate">{detail}</span>}
        {ev.prompt_tokens !== undefined && (
          <span className="text-[10px] text-muted-foreground/60 shrink-0 ml-auto">
            {ev.prompt_tokens}p + {ev.completion_tokens}c tok
          </span>
        )}
        {ev.confidence !== undefined && (
          <span className="text-[10px] text-muted-foreground/60 ml-auto">
            conf {(ev.confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>
    </div>
  );
}

// ── Execution detail panel ────────────────────────────────────────────

function ExecutionDetail({ executionId }: { executionId: string }) {
  const [detail, setDetail] = useState<LogDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<LogDetail>(`/api/v1/logs/${executionId}`)
      .then(setDetail)
      .catch((e) => logger.warn("log detail load failed", { error: String(e) }))
      .finally(() => setLoading(false));
  }, [executionId]);

  if (loading) {
    return (
      <div className="p-3 space-y-1.5">
        {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-6 w-full" />)}
      </div>
    );
  }

  if (!detail) return <p className="px-3 py-2 text-xs text-muted-foreground">Failed to load events.</p>;
  if (detail.timeline.length === 0) return <p className="px-3 py-2 text-xs text-muted-foreground italic">No events recorded for this execution.</p>;

  return (
    <div className="border-t border-border/30 bg-muted/10">
      {/* Skills used */}
      {detail.skills_used?.length > 0 && (
        <div className="px-3 py-2 border-b border-border/20">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-flow-violet/70 mb-1.5 flex items-center gap-1">
            <Sparkles className="h-3 w-3" />
            Skills invoked ({detail.skills_used.length})
          </p>
          <div className="flex flex-wrap gap-1.5">
            {detail.skills_used.map((s) => (
              <span
                key={s.skill_id}
                className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] bg-flow-violet/10 border border-flow-violet/20 text-flow-violet font-mono"
              >
                <Sparkles className="h-2.5 w-2.5" />
                {s.skill_name}
              </span>
            ))}
          </div>
        </div>
      )}
      {/* Answer preview */}
      {detail.timeline.find(e => e.kind === "final")?.answer && (
        <div className="px-3 py-2 border-b border-border/20">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">Answer</p>
          <p className="text-xs text-foreground/80 line-clamp-3">
            {detail.timeline.find(e => e.kind === "final")?.answer}
          </p>
        </div>
      )}
      {/* Error */}
      {detail.error && (
        <div className="px-3 py-2 border-b border-border/20 bg-destructive/5">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-red-400 mb-1">Error</p>
          <p className="text-xs text-red-300 font-mono">{detail.error}</p>
        </div>
      )}
      {/* Timeline */}
      <div className="py-1">
        {detail.timeline.map((ev) => <EventRow key={ev.id} ev={ev} />)}
      </div>
    </div>
  );
}

// ── Execution row ─────────────────────────────────────────────────────

function ExecutionLogRow({ exec }: { exec: ExecutionRow }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={cn("border-b border-border/30 last:border-0 transition-colors", expanded && "bg-muted/5")}>
      <button
        type="button"
        className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-muted/20 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        {/* Expand icon */}
        <span className="mt-0.5 text-muted-foreground/40 shrink-0">
          {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        </span>

        {/* Status dot */}
        <span
          className={cn(
            "mt-1.5 h-2 w-2 rounded-full shrink-0",
            exec.status === "completed" ? "bg-emerald-500" :
            exec.status === "failed" ? "bg-red-500" :
            "bg-amber-500 animate-pulse",
          )}
        />

        {/* Main content */}
        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold">{exec.agent_name}</span>
            <StatusBadge status={exec.status} />
            <span className="text-[10px] text-muted-foreground/60 font-mono">{exec.id.slice(0, 8)}</span>
          </div>
          {exec.user_message && (
            <p className="text-[11px] text-foreground/70 truncate max-w-2xl">{exec.user_message}</p>
          )}
          {/* Stats row */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-[10px] text-muted-foreground/60 flex items-center gap-1">
              <Clock className="h-3 w-3" />{timeAgo(exec.created_at)}
            </span>
            {exec.duration_ms !== null && (
              <span className="text-[10px] text-muted-foreground/60 flex items-center gap-1">
                <Gauge className="h-3 w-3" />{fmtDuration(exec.duration_ms)}
              </span>
            )}
            {exec.node_count > 0 && (
              <span className="text-[10px] text-muted-foreground/60 flex items-center gap-1">
                <Zap className="h-3 w-3" />{exec.node_count} nodes
              </span>
            )}
            {exec.node_count > 0 && (
              <Link
                href={`/executions/${exec.id}`}
                onClick={(e) => e.stopPropagation()}
                className="text-[10px] text-flow-400 hover:text-flow-200 flex items-center gap-1 transition-colors"
              >
                <Activity className="h-3 w-3" />Replay
              </Link>
            )}
            {exec.tool_count > 0 && (
              <span className="text-[10px] text-muted-foreground/60 flex items-center gap-1">
                <Code2 className="h-3 w-3" />{exec.tool_count} tools
              </span>
            )}
            {exec.total_tokens !== null && (
              <span className="text-[10px] text-muted-foreground/60 flex items-center gap-1">
                <Terminal className="h-3 w-3" />{fmtTokens(exec.total_tokens)}
              </span>
            )}
          </div>
        </div>

        <span className="text-[10px] text-muted-foreground/40 shrink-0 tabular-nums pt-0.5">
          {new Date(exec.created_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
        </span>
      </button>

      {expanded && <ExecutionDetail executionId={exec.id} />}
    </div>
  );
}

// ── Live feed ─────────────────────────────────────────────────────────

type LiveEvent = {
  id: string;
  kind: string;
  ts: number;
  payload: Record<string, unknown>;
};

const LIVE_KIND_CONFIG: Record<string, { icon: React.FC<{ className?: string }>; color: string; label: string }> = {
  "digest.start":           { icon: BookOpen,     color: "text-violet-400",  label: "Digest started" },
  "digest.fetch_done":      { icon: BookOpen,     color: "text-sky-400",     label: "Papers fetched" },
  "digest.scoring":         { icon: Zap,          color: "text-amber-400",   label: "Scoring relevance" },
  "digest.filter_done":     { icon: Zap,          color: "text-amber-400",   label: "Papers filtered" },
  "digest.summarize_done":  { icon: Sparkles,     color: "text-violet-400",  label: "Papers summarized" },
  "digest.persist_done":    { icon: CheckCircle2, color: "text-emerald-400", label: "Papers saved" },
  "digest.complete":        { icon: CheckCircle2, color: "text-emerald-400", label: "Digest complete" },
  "knowledge.ingest":       { icon: BookOpen,     color: "text-sky-400",     label: "Knowledge ingested" },
  "execution.start":        { icon: Activity,     color: "text-blue-400",    label: "Execution started" },
  "execution.done":         { icon: CheckCircle2, color: "text-emerald-400", label: "Execution done" },
  "skill.training.started": { icon: BrainCircuit, color: "text-flow-violet", label: "Training started" },
  "skill.training.epoch":   { icon: TrendingUp,   color: "text-amber-400",   label: "Training epoch" },
  "skill.training.done":    { icon: CheckCircle2, color: "text-emerald-400", label: "Training done" },
  "skill.training.failed":  { icon: AlertTriangle,color: "text-red-400",     label: "Training failed" },
  "eval.started":           { icon: Zap,          color: "text-sky-400",     label: "Eval started" },
  "eval.done":              { icon: CheckCircle2, color: "text-violet-400",  label: "Eval complete" },
};

function LiveFeed({ wsId }: { wsId: string }) {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!wsId) return;
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setConnected(false);

    const apiBase = (process.env.NEXT_PUBLIC_FLOW_API_URL ?? "").replace(/\/$/, "");
    const token = getToken();

    (async () => {
      try {
        const res = await fetch(`${apiBase}/api/v1/stream?workspace_id=${wsId}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: ctrl.signal,
        });
        if (!res.ok || !res.body) return;
        setConnected(true);
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() ?? "";
          for (const line of lines) {
            if (!line.startsWith("data:")) continue;
            try {
              const parsed = JSON.parse(line.slice(5).trim()) as Record<string, unknown>;
              const kind = (parsed.kind as string) ?? "unknown";
              setEvents((prev) => [
                { id: `${Date.now()}-${Math.random()}`, kind, ts: Date.now(), payload: parsed },
                ...prev.slice(0, 199),
              ]);
            } catch { /* malformed line */ }
          }
        }
      } catch (e) {
        if ((e as Error)?.name !== "AbortError") {
          logger.warn("live stream error", { error: String(e) });
        }
      } finally {
        setConnected(false);
      }
    })();

    return () => ctrl.abort();
  }, [wsId]);

  function formatPayload(ev: LiveEvent): string {
    const { kind: _kind, ...rest } = ev.payload;
    if (ev.kind === "digest.complete") {
      return `${rest.persisted ?? 0} persisted / ${rest.filtered ?? 0} filtered / ${rest.fetched ?? 0} fetched`;
    }
    if (ev.kind === "skill.training.epoch") {
      const score = typeof rest.eval_score === "number" ? rest.eval_score.toFixed(3) : "—";
      const accepted = rest.accepted ? " ✓ accepted" : "";
      return `epoch ${rest.epoch ?? "?"} · score ${score}${accepted}`;
    }
    if (ev.kind === "skill.training.done") {
      const score = typeof rest.best_score === "number" ? rest.best_score.toFixed(3) : "—";
      return `best ${score} · ${rest.accepted ? "accepted ✓" : "rejected"}`;
    }
    if (ev.kind === "eval.started") {
      return `${rest.total ?? "?"} items · model ${rest.model ?? ""}`;
    }
    if (ev.kind === "eval.done") {
      const pct = typeof rest.pass_rate === "number" ? `${(rest.pass_rate * 100).toFixed(0)}%` : "—";
      return `pass ${pct} · avg ${typeof rest.avg_score === "number" ? rest.avg_score.toFixed(3) : "—"} · ${rest.scored ?? rest.total ?? "?"} items`;
    }
    const vals = Object.entries(rest)
      .filter(([k]) => k !== "workspace_id")
      .map(([k, v]) => `${k}: ${v}`)
      .join("  ·  ");
    return vals;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className={cn("h-2 w-2 rounded-full", connected ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground/40")} />
        <span className="font-mono text-[11px] text-muted-foreground">
          {connected ? "Connected — listening for events" : "Connecting…"}
        </span>
        {events.length > 0 && (
          <button
            type="button"
            onClick={() => setEvents([])}
            className="ml-auto font-mono text-[10px] text-muted-foreground/50 hover:text-muted-foreground"
          >
            Clear
          </button>
        )}
      </div>

      {events.length === 0 ? (
        <div className="rounded-xl border border-flow-800 px-4 py-12 text-center">
          <Activity className="h-8 w-8 text-muted-foreground/30 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">
            Waiting for events — run a digest or start an agent.
          </p>
        </div>
      ) : (
        <div className="rounded-xl border border-flow-800 overflow-hidden divide-y divide-border/20">
          {events.map((ev) => {
            const cfg = LIVE_KIND_CONFIG[ev.kind] ?? { icon: Terminal, color: "text-muted-foreground", label: ev.kind };
            const Icon = cfg.icon;
            const detail = formatPayload(ev);
            const ts = new Date(ev.ts).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
            return (
              <div key={ev.id} className="flex items-start gap-2.5 px-4 py-2.5 hover:bg-muted/10 transition-colors">
                <span className="text-[10px] text-muted-foreground/40 font-mono pt-0.5 shrink-0 w-[68px]">{ts}</span>
                <Icon className={cn("h-3.5 w-3.5 shrink-0 mt-0.5", cfg.color)} />
                <div className="flex items-baseline gap-2 min-w-0">
                  <span className={cn("text-[11px] font-semibold shrink-0", cfg.color)}>{cfg.label}</span>
                  {detail && <span className="text-[11px] text-foreground/60 truncate">{detail}</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────

type ResearchRunRow = {
  id: string;
  status: "running" | "done" | "failed";
  source: string | null;
  paper_count: number;
  error: string | null;
  started_at: string;
  completed_at: string | null;
  duration_ms: number;
};

type TrainingRunRow = {
  id: string;
  status: string;
  epoch: number;
  baseline_score: number | null;
  best_score: number | null;
  accepted: boolean;
  created_at: string;
  completed_at: string | null;
  skill_id: string;
  skill_name: string;
  agent_id: string;
  agent_name: string;
};

export default function LogsPage() {
  const wsId = useStore((s) => s.workspaces[0]?.id ?? "");
  const [activeTab, setActiveTab] = useState<"executions" | "training" | "research" | "live">("executions");
  const [status, setStatus] = useState<ObsStatus | null>(null);
  const [executions, setExecutions] = useState<ExecutionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [trainingRuns, setTrainingRuns] = useState<TrainingRunRow[]>([]);
  const [trainingLoading, setTrainingLoading] = useState(false);
  const [researchRuns, setResearchRuns] = useState<ResearchRunRow[]>([]);
  const [researchLoading, setResearchLoading] = useState(false);
  const [exportingRunId, setExportingRunId] = useState<string | null>(null);
  const [exportResults, setExportResults] = useState<Record<string, { exported: number; error?: string }>>({});

  const loadTraining = useCallback(async () => {
    setTrainingLoading(true);
    try {
      const data = await apiFetch<{ runs: TrainingRunRow[] }>("/api/v1/skills/training-runs");
      setTrainingRuns(data.runs ?? []);
    } catch (e) {
      logger.warn("training runs load failed", { error: String(e) });
    } finally {
      setTrainingLoading(false);
    }
  }, []);

  const loadResearchRuns = useCallback(async () => {
    setResearchLoading(true);
    try {
      const data = await apiFetch<{ runs: ResearchRunRow[] }>("/api/v1/logs/research?limit=50");
      setResearchRuns(data.runs ?? []);
    } catch (e) {
      logger.warn("research runs load failed", { error: String(e) });
    } finally {
      setResearchLoading(false);
    }
  }, []);

  const handleExportObsidian = useCallback(async (runId: string) => {
    setExportingRunId(runId);
    try {
      const data = await apiFetch<{ exported: number }>(
        `/api/v1/digest/runs/${runId}/export-obsidian`,
        { method: "POST" },
      );
      setExportResults((prev) => ({ ...prev, [runId]: { exported: data.exported } }));
    } catch (e) {
      setExportResults((prev) => ({ ...prev, [runId]: { exported: 0, error: String(e) } }));
    } finally {
      setExportingRunId(null);
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [obsStatus, logsData] = await Promise.all([
        apiFetch<ObsStatus>("/api/v1/logs/status"),
        apiFetch<{ executions: ExecutionRow[] }>("/api/v1/logs"),
      ]);
      setStatus(obsStatus);
      setExecutions(logsData.executions);
    } catch (e) {
      logger.warn("logs load failed", { error: String(e) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const filtered = filterStatus === "all"
    ? executions
    : executions.filter(e => e.status === filterStatus);

  const counts = {
    all: executions.length,
    completed: executions.filter(e => e.status === "completed").length,
    failed: executions.filter(e => e.status === "failed").length,
    running: executions.filter(e => e.status === "running").length,
  };

  return (
    <div className="flex flex-col min-h-screen">
      <FlowPageHeader
        leading={<Terminal className="h-4 w-4 text-muted-foreground" />}
        title="Logs"
        description="Execution traces, LLM calls, tool use"
        actions={
          <Button variant="outline" size="sm" onClick={() => void load()} className="text-xs h-7">
            Refresh
          </Button>
        }
      />

      <div className="mx-auto w-full max-w-5xl px-4 py-6 space-y-4">

        {/* LangSmith banner */}
        {status && (
          <div className={cn(
            "rounded-[6px] border px-4 py-3 flex items-center gap-3 text-sm",
            status.langsmith_enabled
              ? "border-flow-violet/30 bg-flow-violet/5"
              : "border-flow-800 bg-muted/10",
          )}>
            <Bot className={cn("h-4 w-4 shrink-0", status.langsmith_enabled ? "text-flow-violet" : "text-muted-foreground")} />
            <div className="flex-1 min-w-0">
              {status.langsmith_enabled ? (
                <span className="text-sm">
                  LangSmith tracing active — project{" "}
                  <span className="font-mono text-flow-violet">{status.project}</span>
                </span>
              ) : (
                <span className="text-sm text-muted-foreground">
                  LangSmith not configured — add{" "}
                  <span className="font-mono text-xs bg-muted px-1 py-0.5 rounded">FLOW_LANGSMITH_API_KEY</span>{" "}
                  to <span className="font-mono text-xs">.env</span> for full LLM traces
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Badge variant="outline" className="text-[10px] h-5">
                {status.log_level}
              </Badge>
              {status.trace_url && (
                <a
                  href={status.trace_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-xs text-flow-violet hover:underline"
                >
                  Open LangSmith <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          </div>
        )}

        {/* Main tab switcher */}
        <div className="flex gap-1 border-b border-flow-800 pb-0">
          <button
            type="button"
            onClick={() => setActiveTab("executions")}
            className={cn(
              "border-b-2 px-3 pb-2 font-mono text-[11px] font-medium uppercase tracking-wider transition-colors flex items-center gap-1.5",
              activeTab === "executions" ? "border-flow-violet text-flow-50" : "border-transparent text-flow-500 hover:text-flow-300",
            )}
          >
            Executions
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab("training"); void loadTraining(); }}
            className={cn(
              "border-b-2 px-3 pb-2 font-mono text-[11px] font-medium uppercase tracking-wider transition-colors flex items-center gap-1.5",
              activeTab === "training" ? "border-flow-violet text-flow-50" : "border-transparent text-flow-500 hover:text-flow-300",
            )}
          >
            <BrainCircuit className="h-3 w-3" />
            Training
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab("research"); void loadResearchRuns(); }}
            className={cn(
              "border-b-2 px-3 pb-2 font-mono text-[11px] font-medium uppercase tracking-wider transition-colors flex items-center gap-1.5",
              activeTab === "research" ? "border-flow-violet text-flow-50" : "border-transparent text-flow-500 hover:text-flow-300",
            )}
          >
            <BookOpen className="h-3 w-3" />
            Research
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("live")}
            className={cn(
              "border-b-2 px-3 pb-2 font-mono text-[11px] font-medium uppercase tracking-wider transition-colors flex items-center gap-1.5",
              activeTab === "live" ? "border-flow-violet text-flow-50" : "border-transparent text-flow-500 hover:text-flow-300",
            )}
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", activeTab === "live" ? "bg-emerald-400 animate-pulse" : "bg-muted-foreground/40")} />
            Live
          </button>
        </div>

        {activeTab === "live" && <LiveFeed wsId={wsId} />}

        {activeTab === "training" && (
          <>
            {trainingLoading ? (
              <div className="rounded-xl border border-flow-800 overflow-hidden divide-y divide-border/30">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="px-4 py-3 space-y-2">
                    <Skeleton className="h-4 w-48" />
                    <Skeleton className="h-3 w-full max-w-sm" />
                    <Skeleton className="h-3 w-32" />
                  </div>
                ))}
              </div>
            ) : trainingRuns.length === 0 ? (
              <div className="rounded-xl border border-flow-800 px-4 py-12 text-center">
                <BrainCircuit className="h-8 w-8 text-muted-foreground/30 mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">
                  No training runs yet — improve a skill to see history here.
                </p>
              </div>
            ) : (
              <div className="rounded-xl border border-flow-800 overflow-hidden">
                {trainingRuns.map((run) => {
                  const scoreDelta =
                    run.best_score !== null && run.baseline_score !== null
                      ? run.best_score - run.baseline_score
                      : null;
                  const statusCls =
                    run.status === "completed" && run.accepted
                      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                      : run.status === "completed"
                      ? "border-red-500/30 bg-red-500/10 text-red-400"
                      : run.status === "running"
                      ? "border-amber-500/30 bg-amber-500/10 text-amber-400"
                      : "border-flow-800 text-muted-foreground";
                  return (
                    <div
                      key={run.id}
                      className="border-b border-border/30 last:border-0 px-4 py-3 hover:bg-muted/10 transition-colors"
                    >
                      <div className="flex items-start gap-3">
                        <BrainCircuit className="h-4 w-4 text-flow-violet/60 mt-0.5 shrink-0" />
                        <div className="flex-1 min-w-0 space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-semibold">{run.skill_name}</span>
                            <span className="text-[10px] text-muted-foreground/50">·</span>
                            <span className="text-[10px] text-muted-foreground/60">{run.agent_name}</span>
                            <Badge variant="outline" className={cn("text-[10px] px-1.5 h-5 capitalize", statusCls)}>
                              {run.accepted ? "accepted" : run.status}
                            </Badge>
                            <span className="text-[10px] text-muted-foreground/40 font-mono">{run.id.slice(0, 8)}</span>
                          </div>
                          <div className="flex items-center gap-3 flex-wrap">
                            {run.baseline_score !== null && (
                              <span className="text-[10px] text-muted-foreground/60 flex items-center gap-1">
                                <TrendingUp className="h-3 w-3" />
                                {run.baseline_score.toFixed(2)}
                                {scoreDelta !== null && (
                                  <span className={cn("ml-1 font-semibold", scoreDelta > 0 ? "text-emerald-400" : scoreDelta < 0 ? "text-red-400" : "text-muted-foreground")}>
                                    {scoreDelta > 0 ? "+" : ""}{scoreDelta.toFixed(2)}
                                  </span>
                                )}
                                {run.best_score !== null && (
                                  <span className="text-muted-foreground/40">→ {run.best_score.toFixed(2)}</span>
                                )}
                              </span>
                            )}
                            {run.epoch > 0 && (
                              <span className="text-[10px] text-muted-foreground/60 flex items-center gap-1">
                                <Zap className="h-3 w-3" />{run.epoch} epoch{run.epoch !== 1 ? "s" : ""}
                              </span>
                            )}
                            <span className="text-[10px] text-muted-foreground/50 flex items-center gap-1">
                              <Clock className="h-3 w-3" />{timeAgo(run.created_at)}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}

        {activeTab === "research" && (
          <div className="space-y-2">
            {researchLoading && (
              <div className="flex items-center gap-2 py-4 text-xs text-flow-500">
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-flow-500 border-t-transparent" />
                Loading research runs…
              </div>
            )}
            {!researchLoading && researchRuns.length === 0 && (
              <div className="rounded-xl border border-dashed border-flow-800 py-10 text-center">
                <p className="font-mono text-xs text-flow-500">No research digests yet</p>
              </div>
            )}
            {!researchLoading && researchRuns.map((run) => {
              const expResult = exportResults[run.id];
              const isExporting = exportingRunId === run.id;
              return (
                <div key={run.id} className="flex items-center gap-3 rounded-lg border border-flow-800 bg-flow-900/50 px-4 py-3">
                  <span className={cn(
                    "h-2 w-2 rounded-full shrink-0",
                    run.status === "running" ? "bg-flow-violet animate-pulse" :
                    run.status === "done" ? "bg-emerald-500" : "bg-red-500",
                  )} />
                  <div className="flex-1 min-w-0">
                    <p className="truncate font-mono text-xs font-medium text-flow-100">
                      {run.source ?? "digest"} · {run.paper_count} paper{run.paper_count !== 1 ? "s" : ""}
                    </p>
                    {run.error && (
                      <p className="truncate font-mono text-[10px] text-red-400">{run.error}</p>
                    )}
                  </div>
                  {expResult && !expResult.error && (
                    <span className="flex items-center gap-1 font-mono text-[10px] text-emerald-400">
                      ✓ {expResult.exported} notes
                    </span>
                  )}
                  {expResult?.error && (
                    <span className="truncate max-w-[120px] font-mono text-[10px] text-red-400">{expResult.error}</span>
                  )}
                  <button
                    disabled={isExporting || run.status !== "done"}
                    onClick={() => void handleExportObsidian(run.id)}
                    className={cn(
                      "shrink-0 rounded border px-2 py-1 font-mono text-[10px] transition-colors",
                      run.status === "done" && !isExporting
                        ? "border-flow-700 bg-flow-800 text-flow-300 hover:bg-flow-700 hover:text-flow-100"
                        : "cursor-not-allowed border-flow-800 bg-flow-950 text-flow-600 opacity-50",
                    )}
                  >
                    {isExporting ? "Exporting…" : "Export to Obsidian"}
                  </button>
                  {run.duration_ms > 0 && (
                    <span className="shrink-0 font-mono text-[10px] text-flow-600">
                      {(run.duration_ms / 1000).toFixed(1)}s
                    </span>
                  )}
                  <span className="shrink-0 font-mono text-[10px] text-flow-600">
                    {new Date(run.started_at).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {activeTab === "executions" && <>
        {/* Filter tabs */}
        <div className="flex items-center gap-1">
          {(["all", "completed", "failed", "running"] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setFilterStatus(s)}
              className={cn(
                "px-3 py-1 text-xs rounded-md transition-colors capitalize",
                filterStatus === s
                  ? "bg-flow-800 text-foreground font-semibold"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/40",
              )}
            >
              {s}
              <span className="ml-1.5 text-[10px] text-muted-foreground/60 tabular-nums">
                {counts[s]}
              </span>
            </button>
          ))}
        </div>

        {/* Execution log list */}
        {loading ? (
          <div className="rounded-xl border border-flow-800 overflow-hidden divide-y divide-border/30">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="px-4 py-3 space-y-2">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-3 w-full max-w-sm" />
                <Skeleton className="h-3 w-32" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-xl border border-flow-800 px-4 py-12 text-center">
            <Terminal className="h-8 w-8 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">
              {filterStatus === "all"
                ? "No executions yet — run an agent to see logs here."
                : `No ${filterStatus} executions.`}
            </p>
          </div>
        ) : (
          <div className="rounded-xl border border-flow-800 overflow-hidden">
            {filtered.map((exec) => (
              <ExecutionLogRow key={exec.id} exec={exec} />
            ))}
          </div>
        )}
        </>}
      </div>
    </div>
  );
}
