"use client";

import { useEffect, useState, useMemo } from "react";
import {
  Calendar,
  Clock,
  Play,
  Pause,
  Plus,
  Trash2,
  Webhook,
  Zap,
  ChevronRight,
  Timer,
  RefreshCw,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { apiFetch } from "@/lib/api";
import { logger } from "@/lib/logger";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";

type Schedule = {
  id: string;
  agent_id: string;
  agent_name: string;
  cron_expr: string;
  prompt_template: string;
  delivery_type: "none" | "webhook";
  delivery_target: string | null;
  enabled: boolean;
  last_run_at: string | null;
  created_at: string;
};

type AgentRow = { id: string; name: string };

type CronJob = {
  name: string;
  cron_expr: string;
  human_readable: string;
  next_run: string;
  description: string;
};

const QUICK_CRONS = [
  { label: "Every hour", value: "0 * * * *", desc: "Runs at the top of every hour" },
  { label: "Daily 8 AM", value: "0 8 * * *", desc: "Every morning at 8:00 AM UTC" },
  { label: "Daily 3 AM", value: "0 3 * * *", desc: "Every night at 3:00 AM UTC" },
  { label: "Weekly Mon", value: "0 9 * * 1", desc: "Every Monday at 9:00 AM UTC" },
];

function parseCronHuman(expr: string): string {
  const match = QUICK_CRONS.find((q) => q.value === expr);
  if (match) return match.desc;
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return "Custom schedule";
  const [min, hour, dom, , dow] = parts;
  if (min === "*" && hour === "*") return "Every minute of every hour";
  if (min !== "*" && hour !== "*" && dom === "*" && dow === "*")
    return `Every day at ${hour.padStart(2, "0")}:${min.padStart(2, "0")} UTC`;
  if (min !== "*" && hour !== "*" && dow !== "*")
    return `Weekly on day ${dow} at ${hour.padStart(2, "0")}:${min.padStart(2, "0")} UTC`;
  return "Custom schedule";
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function nextRunLabel(next_run: string): string {
  const diff = new Date(next_run).getTime() - Date.now();
  const m = Math.round(diff / 60000);
  if (m <= 0) return "now";
  if (m < 60) return `in ${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `in ${h}h`;
  return `in ${Math.floor(h / 24)}d`;
}

// ─── Empty state (no schedules yet) ──────────────────────────────────────────
function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-5 text-center px-8">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted/50 border border-border/40">
        <Calendar className="h-7 w-7 text-muted-foreground/50" />
      </div>
      <div className="space-y-1.5">
        <p className="text-sm font-semibold text-foreground">No schedules yet</p>
        <p className="text-xs text-muted-foreground max-w-[260px] leading-relaxed">
          Schedules run an agent automatically on a cron — daily briefings, weekly reports, nightly evals.
        </p>
      </div>
      <Button size="sm" onClick={onNew} className="gap-1.5 h-8 text-xs">
        <Plus className="h-3.5 w-3.5" />
        New schedule
      </Button>
    </div>
  );
}

// ─── Schedule list item ───────────────────────────────────────────────────────
function ScheduleItem({
  s,
  selected,
  onClick,
}: {
  s: Schedule;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full text-left rounded-xl border px-3 py-2.5 transition-all group",
        selected
          ? "border-flow-brand/40 bg-flow-brand/5"
          : "border-border/40 bg-card/40 hover:border-border/70 hover:bg-card/70",
        !s.enabled && "opacity-60",
      )}
    >
      <div className="flex items-start gap-2.5">
        <div
          className={cn(
            "mt-0.5 h-2 w-2 rounded-full shrink-0",
            s.enabled ? "bg-emerald-400" : "bg-muted-foreground/30",
          )}
        />
        <div className="flex-1 min-w-0 space-y-0.5">
          <p className="text-[13px] font-medium text-foreground truncate">{s.agent_name}</p>
          <p className="text-[11px] text-muted-foreground font-mono">{s.cron_expr}</p>
          {s.last_run_at && (
            <p className="text-[10px] text-muted-foreground/60 flex items-center gap-1">
              <Clock className="h-2.5 w-2.5" />
              {relativeTime(s.last_run_at)}
            </p>
          )}
        </div>
        <ChevronRight
          className={cn(
            "h-3.5 w-3.5 text-muted-foreground/40 mt-1 shrink-0 transition-transform",
            selected && "rotate-90 text-flow-brand/60",
          )}
        />
      </div>
    </button>
  );
}

// ─── Create form (right panel) ────────────────────────────────────────────────
function CreateForm({
  agents,
  onCreated,
  workspaceId,
}: {
  agents: AgentRow[];
  onCreated: (s: Schedule) => void;
  workspaceId: string;
}) {
  const [form, setForm] = useState({
    agent_id: "",
    cron_expr: "0 8 * * *",
    prompt_template: "Summarize the latest AI research papers from today.",
    delivery_type: "none",
    delivery_target: "",
  });
  const [creating, setCreating] = useState(false);
  const humanCron = useMemo(() => parseCronHuman(form.cron_expr), [form.cron_expr]);

  async function handleCreate() {
    if (!form.agent_id) return;
    setCreating(true);
    try {
      const result = await apiFetch<{ id: string }>("/api/v1/schedules", {
        method: "POST",
        json: {
          workspace_id: workspaceId,
          agent_id: form.agent_id,
          cron_expr: form.cron_expr,
          prompt_template: form.prompt_template,
          delivery_type: form.delivery_type,
          delivery_target: form.delivery_target || null,
        },
      });
      const agent = agents.find((a) => a.id === form.agent_id);
      onCreated({
        id: result.id,
        agent_id: form.agent_id,
        agent_name: agent?.name ?? "Unknown",
        cron_expr: form.cron_expr,
        prompt_template: form.prompt_template,
        delivery_type: form.delivery_type as "none" | "webhook",
        delivery_target: form.delivery_target || null,
        enabled: true,
        last_run_at: null,
        created_at: new Date().toISOString(),
      });
    } catch (err) {
      logger.warn("create schedule failed", { error: String(err) });
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="border-b border-border/40 px-6 py-4">
        <p className="text-sm font-semibold text-foreground">New schedule</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          Pick an agent and a cadence — the rest is automatic.
        </p>
      </div>

      <div className="flex-1 overflow-auto px-6 py-5 space-y-6">
        {/* Agent */}
        <div className="space-y-2">
          <Label className="text-xs font-semibold text-foreground/80 uppercase tracking-wide">Agent</Label>
          <Select
            value={form.agent_id}
            onValueChange={(v) => setForm((f) => ({ ...f, agent_id: v ?? "" }))}
          >
            <SelectTrigger className="h-9 text-sm">
              <SelectValue placeholder="Select an agent…" />
            </SelectTrigger>
            <SelectContent>
              {agents.map((a) => (
                <SelectItem key={a.id} value={a.id} className="text-sm">
                  {a.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Cadence */}
        <div className="space-y-2">
          <Label className="text-xs font-semibold text-foreground/80 uppercase tracking-wide">
            Cadence
          </Label>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {QUICK_CRONS.map((q) => (
              <button
                key={q.value}
                type="button"
                onClick={() => setForm((f) => ({ ...f, cron_expr: q.value }))}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-xs border font-medium transition-all",
                  form.cron_expr === q.value
                    ? "bg-flow-brand/10 border-flow-brand/40 text-flow-brand"
                    : "border-border/50 text-muted-foreground hover:text-foreground hover:border-border",
                )}
              >
                {q.label}
              </button>
            ))}
          </div>
          <Input
            value={form.cron_expr}
            onChange={(e) => setForm((f) => ({ ...f, cron_expr: e.target.value }))}
            placeholder="0 8 * * *"
            className="h-9 text-sm font-mono"
          />
          <p className="text-xs text-muted-foreground flex items-center gap-1.5">
            <Timer className="h-3 w-3 shrink-0" />
            {humanCron}
          </p>
        </div>

        {/* Prompt */}
        <div className="space-y-2">
          <Label className="text-xs font-semibold text-foreground/80 uppercase tracking-wide">
            Prompt
          </Label>
          <p className="text-xs text-muted-foreground -mt-1">
            What the agent runs each time the schedule fires.
          </p>
          <Textarea
            value={form.prompt_template}
            onChange={(e) => setForm((f) => ({ ...f, prompt_template: e.target.value }))}
            rows={3}
            className="text-sm resize-none"
          />
        </div>

        {/* Delivery */}
        <div className="space-y-2">
          <Label className="text-xs font-semibold text-foreground/80 uppercase tracking-wide">
            Delivery
          </Label>
          <Select
            value={form.delivery_type}
            onValueChange={(v) => setForm((f) => ({ ...f, delivery_type: v ?? "none" }))}
          >
            <SelectTrigger className="h-9 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none" className="text-sm">No delivery — run only</SelectItem>
              <SelectItem value="webhook" className="text-sm">
                <span className="flex items-center gap-1.5">
                  <Webhook className="h-3.5 w-3.5" />
                  Webhook POST
                </span>
              </SelectItem>
            </SelectContent>
          </Select>
          {form.delivery_type === "webhook" && (
            <Input
              value={form.delivery_target}
              onChange={(e) => setForm((f) => ({ ...f, delivery_target: e.target.value }))}
              placeholder="https://hooks.example.com/…"
              className="h-9 text-sm"
            />
          )}
        </div>
      </div>

      <div className="border-t border-border/40 px-6 py-4 flex gap-2">
        <Button
          onClick={handleCreate}
          disabled={creating || !form.agent_id}
          className="gap-1.5 text-sm"
        >
          <Play className="h-3.5 w-3.5" />
          {creating ? "Creating…" : "Create schedule"}
        </Button>
      </div>
    </div>
  );
}

// ─── Schedule detail (right panel) ───────────────────────────────────────────
function ScheduleDetail({
  s,
  cronJobs,
  onToggle,
  onDelete,
}: {
  s: Schedule;
  cronJobs: CronJob[];
  onToggle: (id: string, current: boolean) => void;
  onDelete: (id: string) => void;
}) {
  const humanCron = parseCronHuman(s.cron_expr);

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b border-border/40 px-6 py-4 flex items-start justify-between gap-4">
        <div className="space-y-0.5 min-w-0">
          <p className="text-sm font-semibold text-foreground">{s.agent_name}</p>
          <p className="text-xs text-muted-foreground font-mono">{s.cron_expr}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs text-muted-foreground">{s.enabled ? "Active" : "Paused"}</span>
          <Switch
            checked={s.enabled}
            onCheckedChange={() => onToggle(s.id, s.enabled)}
          />
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto px-6 py-5 space-y-6">
        {/* Status strip */}
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-xl border border-border/40 bg-card/40 px-4 py-3 space-y-1">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Status</p>
            <div className="flex items-center gap-1.5">
              <span
                className={cn(
                  "h-2 w-2 rounded-full",
                  s.enabled ? "bg-emerald-400" : "bg-muted-foreground/30",
                )}
              />
              <span className="text-sm font-semibold">{s.enabled ? "Active" : "Paused"}</span>
            </div>
          </div>
          <div className="rounded-xl border border-border/40 bg-card/40 px-4 py-3 space-y-1">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Last run</p>
            <p className="text-sm font-semibold">
              {s.last_run_at ? relativeTime(s.last_run_at) : "—"}
            </p>
          </div>
          <div className="rounded-xl border border-border/40 bg-card/40 px-4 py-3 space-y-1">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Created</p>
            <p className="text-sm font-semibold">{relativeTime(s.created_at)}</p>
          </div>
        </div>

        {/* Cadence */}
        <div className="space-y-2">
          <p className="text-xs font-semibold text-foreground/60 uppercase tracking-wide">Cadence</p>
          <div className="rounded-xl border border-border/40 bg-card/40 px-4 py-3 space-y-1.5">
            <p className="text-sm font-mono font-medium">{s.cron_expr}</p>
            <p className="text-xs text-muted-foreground flex items-center gap-1.5">
              <Timer className="h-3 w-3 shrink-0" />
              {humanCron}
            </p>
          </div>
        </div>

        {/* Prompt */}
        <div className="space-y-2">
          <p className="text-xs font-semibold text-foreground/60 uppercase tracking-wide">Prompt</p>
          <div className="rounded-xl border border-border/40 bg-card/40 px-4 py-3">
            <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">{s.prompt_template}</p>
          </div>
        </div>

        {/* Delivery */}
        {s.delivery_type !== "none" && (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-foreground/60 uppercase tracking-wide">Delivery</p>
            <div className="rounded-xl border border-border/40 bg-card/40 px-4 py-3 flex items-center gap-2">
              <Webhook className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <p className="text-sm font-mono text-muted-foreground break-all">{s.delivery_target}</p>
            </div>
          </div>
        )}

        <Separator />

        {/* Danger zone */}
        <div className="space-y-2">
          <p className="text-xs font-semibold text-foreground/60 uppercase tracking-wide">Actions</p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5 text-xs h-8"
              onClick={() => onToggle(s.id, s.enabled)}
            >
              {s.enabled ? (
                <>
                  <Pause className="h-3 w-3" />
                  Pause schedule
                </>
              ) : (
                <>
                  <Play className="h-3 w-3" />
                  Resume schedule
                </>
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5 text-xs h-8 text-destructive hover:text-destructive border-destructive/30 hover:border-destructive/60"
              onClick={() => onDelete(s.id)}
            >
              <Trash2 className="h-3 w-3" />
              Delete
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── System jobs (collapsed footer) ──────────────────────────────────────────
function SystemJobsBadge({ jobs }: { jobs: CronJob[] }) {
  const [open, setOpen] = useState(false);
  if (jobs.length === 0) return null;
  return (
    <div className="border-t border-border/30 bg-muted/20">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <span className="flex items-center gap-2">
          <Zap className="h-3 w-3" />
          System background jobs ({jobs.length})
        </span>
        <ChevronRight className={cn("h-3 w-3 transition-transform", open && "rotate-90")} />
      </button>
      {open && (
        <div className="px-4 pb-3 space-y-1.5">
          {jobs.map((job) => (
            <div
              key={job.name}
              className="flex items-center gap-3 rounded-lg border border-border/30 bg-card/30 px-3 py-2"
            >
              <div className="flex-1 min-w-0 space-y-0.5">
                <p className="text-xs font-mono font-medium">{job.name}</p>
                <p className="text-[11px] text-muted-foreground">{job.description}</p>
              </div>
              <div className="text-right shrink-0">
                <Badge variant="outline" className="font-mono text-[10px]">
                  {job.cron_expr}
                </Badge>
                <p className="text-[10px] text-muted-foreground mt-1">
                  {nextRunLabel(job.next_run)}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function SchedulesPage() {
  const workspaces = useStore((s) => s.workspaces);
  const workspaceId = workspaces[0]?.id ?? null;

  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [cronJobs, setCronJobs] = useState<CronJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<"list" | "new" | { id: string }>("list");

  useEffect(() => {
    if (!workspaceId) return;
    setLoading(true);
    Promise.all([
      apiFetch<{ schedules: Schedule[] }>(`/api/v1/schedules?workspace_id=${workspaceId}`),
      apiFetch<{ agents: AgentRow[] }>(`/api/v1/workspaces/${workspaceId}/agents`),
      apiFetch<{ cron_jobs: CronJob[] }>(`/api/v1/schedules/cron-jobs`),
    ])
      .then(([sData, aData, cData]) => {
        setSchedules(sData.schedules ?? []);
        setAgents(aData.agents ?? []);
        setCronJobs(cData.cron_jobs ?? []);
      })
      .catch((e) => logger.warn("schedules load failed", { error: String(e) }))
      .finally(() => setLoading(false));
  }, [workspaceId]);

  const selectedId = typeof view === "object" ? view.id : null;
  const selectedSchedule = selectedId ? schedules.find((s) => s.id === selectedId) ?? null : null;

  async function handleToggle(id: string, current: boolean) {
    try {
      await apiFetch(`/api/v1/schedules/${id}/toggle`, {
        method: "PATCH",
        json: { enabled: !current },
      });
      setSchedules((prev) => prev.map((s) => (s.id === id ? { ...s, enabled: !current } : s)));
    } catch (err) {
      logger.warn("toggle failed", { error: String(err) });
    }
  }

  async function handleDelete(id: string) {
    try {
      await apiFetch(`/api/v1/schedules/${id}?workspace_id=${workspaceId}`, { method: "DELETE" });
      setSchedules((prev) => prev.filter((s) => s.id !== id));
      setView("list");
    } catch (err) {
      logger.warn("delete failed", { error: String(err) });
    }
  }

  function handleCreated(s: Schedule) {
    setSchedules((prev) => [s, ...prev]);
    setView({ id: s.id });
  }

  return (
    <div className="flex h-full flex-col">
      <FlowPageHeader title="Schedules" />

      <div className="flex flex-1 overflow-hidden">
        {/* ── Left sidebar: schedule list ──────────────────────── */}
        <div className="flex w-64 flex-col border-r border-border/40 bg-muted/10">
          {/* Toolbar */}
          <div className="flex items-center justify-between px-3 py-3 border-b border-border/30">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Schedules
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => {
                  if (!workspaceId) return;
                  setLoading(true);
                  Promise.all([
                    apiFetch<{ schedules: Schedule[] }>(`/api/v1/schedules?workspace_id=${workspaceId}`),
                    apiFetch<{ agents: AgentRow[] }>(`/api/v1/workspaces/${workspaceId}/agents`),
                  ])
                    .then(([sData, aData]) => {
                      setSchedules(sData.schedules ?? []);
                      setAgents(aData.agents ?? []);
                    })
                    .catch((e) => logger.warn("schedules refresh failed", { error: String(e) }))
                    .finally(() => setLoading(false));
                }}
                title="Refresh"
              >
                <RefreshCw className={cn("h-3 w-3 text-muted-foreground", loading && "animate-spin")} />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className={cn("h-6 w-6", view === "new" && "bg-flow-brand/10 text-flow-brand")}
                onClick={() => setView("new")}
                title="New schedule"
              >
                <Plus className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>

          {/* List */}
          <div className="flex-1 overflow-auto p-2 space-y-1.5">
            {loading ? (
              <div className="flex items-center justify-center py-8 gap-2 text-xs text-muted-foreground">
                <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-flow-brand border-t-transparent" />
                Loading…
              </div>
            ) : schedules.length === 0 ? (
              <p className="text-center text-xs text-muted-foreground py-8 px-3 leading-relaxed">
                No schedules yet.
                <br />
                <button
                  onClick={() => setView("new")}
                  className="text-flow-brand hover:underline mt-1 block mx-auto"
                >
                  Create one →
                </button>
              </p>
            ) : (
              schedules.map((s) => (
                <ScheduleItem
                  key={s.id}
                  s={s}
                  selected={selectedId === s.id}
                  onClick={() => setView({ id: s.id })}
                />
              ))
            )}
          </div>

          {/* System jobs footer */}
          <SystemJobsBadge jobs={cronJobs} />
        </div>

        {/* ── Right panel ─────────────────────────────────────── */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {view === "new" && workspaceId ? (
            <CreateForm agents={agents} onCreated={handleCreated} workspaceId={workspaceId} />
          ) : selectedSchedule ? (
            <ScheduleDetail
              s={selectedSchedule}
              cronJobs={cronJobs}
              onToggle={handleToggle}
              onDelete={handleDelete}
            />
          ) : (
            <EmptyState onNew={() => setView("new")} />
          )}
        </div>
      </div>
    </div>
  );
}
