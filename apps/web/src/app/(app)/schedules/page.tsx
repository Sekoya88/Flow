"use client";

import { useEffect, useState } from "react";
import { Calendar, Clock, Play, Plus, Trash2, Webhook, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { apiFetch } from "@/lib/api";
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
  { label: "Every hour", value: "0 * * * *" },
  { label: "Daily 8AM", value: "0 8 * * *" },
  { label: "Daily 3AM", value: "0 3 * * *" },
  { label: "Weekly Mon", value: "0 9 * * 1" },
];

export default function SchedulesPage() {
  const workspaces = useStore((s) => s.workspaces);
  const workspaceId = workspaces[0]?.id ?? null;

  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [cronJobs, setCronJobs] = useState<CronJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    agent_id: "",
    cron_expr: "0 8 * * *",
    prompt_template: "Summarize the latest AI research papers from today.",
    delivery_type: "none",
    delivery_target: "",
  });

  useEffect(() => {
    if (!workspaceId) return;
    setLoading(true);
    Promise.all([
      apiFetch<{ schedules: Schedule[] }>(`/api/v1/schedules?workspace_id=${workspaceId}`),
      apiFetch<{ agents: AgentRow[] }>(`/api/v1/agents?workspace_id=${workspaceId}`),
      apiFetch<{ cron_jobs: CronJob[] }>(`/api/v1/schedules/cron-jobs`),
    ])
      .then(([sData, aData, cData]) => {
        setSchedules(sData.schedules ?? []);
        setAgents(aData.agents ?? []);
        setCronJobs(cData.cron_jobs ?? []);
      })
      .catch(console.warn)
      .finally(() => setLoading(false));
  }, [workspaceId]);

  async function handleCreate() {
    if (!workspaceId || !form.agent_id) return;
    setCreating(true);
    try {
      const result = await apiFetch<{ id: string }>("/api/v1/schedules", {
        method: "POST",
        body: JSON.stringify({
          workspace_id: workspaceId,
          agent_id: form.agent_id,
          cron_expr: form.cron_expr,
          prompt_template: form.prompt_template,
          delivery_type: form.delivery_type,
          delivery_target: form.delivery_target || null,
        }),
      });
      const agent = agents.find((a) => a.id === form.agent_id);
      setSchedules((prev) => [
        {
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
        },
        ...prev,
      ]);
      setShowForm(false);
    } catch (err) {
      console.warn("create schedule failed:", err);
    } finally {
      setCreating(false);
    }
  }

  async function handleToggle(id: string, current: boolean) {
    try {
      await apiFetch(`/api/v1/schedules/${id}/toggle`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: !current }),
      });
      setSchedules((prev) => prev.map((s) => (s.id === id ? { ...s, enabled: !current } : s)));
    } catch (err) {
      console.warn("toggle failed:", err);
    }
  }

  async function handleDelete(id: string) {
    try {
      await apiFetch(`/api/v1/schedules/${id}?workspace_id=${workspaceId}`, { method: "DELETE" });
      setSchedules((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      console.warn("delete failed:", err);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <FlowPageHeader title="Schedules" />
      <div className="flex-1 overflow-auto p-6 space-y-6 max-w-4xl">

        {/* ── System Cron Jobs ─────────────────────────── */}
        {cronJobs.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-3">
              <Zap className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-sm font-semibold text-foreground">System jobs</h2>
              <span className="text-xs text-muted-foreground">— background tasks managed by the worker</span>
            </div>
            <div className="grid gap-2">
              {cronJobs.map((job) => (
                <div
                  key={job.name}
                  className="flex items-center gap-4 rounded-xl border border-border/50 bg-card/60 px-4 py-3"
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted/50">
                    <Zap className="h-3.5 w-3.5 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium font-mono">{job.name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{job.description}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="flex items-center gap-1.5 justify-end">
                      <Badge variant="outline" className="font-mono text-[10px]">{job.cron_expr}</Badge>
                      <span className="text-xs text-muted-foreground hidden sm:block">{job.human_readable}</span>
                    </div>
                    <p className="text-[11px] text-muted-foreground mt-1 font-mono">
                      next: {new Date(job.next_run).toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ── Agent Schedules ──────────────────────────── */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-sm font-semibold text-foreground">Agent schedules</h2>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="gap-1.5 h-8 text-xs"
              onClick={() => setShowForm((v) => !v)}
            >
              <Plus className="h-3.5 w-3.5" />
              New schedule
            </Button>
          </div>

          {/* Create form */}
          {showForm && (
            <Card className="mb-4 border-flow-brand/20 bg-card/80">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">New schedule</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-xs">Agent</Label>
                    <Select
                      value={form.agent_id}
                      onValueChange={(v) => setForm((f) => ({ ...f, agent_id: v ?? "" }))}
                    >
                      <SelectTrigger className="h-8 text-xs">
                        <SelectValue placeholder="Select agent…" />
                      </SelectTrigger>
                      <SelectContent>
                        {agents.map((a) => (
                          <SelectItem key={a.id} value={a.id} className="text-xs">{a.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs">Cron expression</Label>
                    <div className="space-y-1.5">
                      <Input
                        value={form.cron_expr}
                        onChange={(e) => setForm((f) => ({ ...f, cron_expr: e.target.value }))}
                        placeholder="0 8 * * *"
                        className="h-8 text-xs font-mono"
                      />
                      <div className="flex flex-wrap gap-1">
                        {QUICK_CRONS.map((q) => (
                          <button
                            key={q.value}
                            type="button"
                            onClick={() => setForm((f) => ({ ...f, cron_expr: q.value }))}
                            className={cn(
                              "rounded-md px-2 py-0.5 text-[10px] border transition-colors",
                              form.cron_expr === q.value
                                ? "bg-flow-brand/10 border-flow-brand/30 text-flow-brand"
                                : "border-border/50 text-muted-foreground hover:text-foreground",
                            )}
                          >
                            {q.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs">Prompt (what the agent runs)</Label>
                  <Textarea
                    value={form.prompt_template}
                    onChange={(e) => setForm((f) => ({ ...f, prompt_template: e.target.value }))}
                    rows={2}
                    className="text-xs resize-none"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-xs">Delivery</Label>
                    <Select
                      value={form.delivery_type}
                      onValueChange={(v) => setForm((f) => ({ ...f, delivery_type: v ?? "none" }))}
                    >
                      <SelectTrigger className="h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none" className="text-xs">No delivery</SelectItem>
                        <SelectItem value="webhook" className="text-xs">Webhook POST</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {form.delivery_type === "webhook" && (
                    <div className="space-y-1.5">
                      <Label className="text-xs">Webhook URL</Label>
                      <Input
                        value={form.delivery_target}
                        onChange={(e) => setForm((f) => ({ ...f, delivery_target: e.target.value }))}
                        placeholder="https://hooks.example.com/…"
                        className="h-8 text-xs"
                      />
                    </div>
                  )}
                </div>

                <div className="flex gap-2 pt-1">
                  <Button
                    size="sm"
                    onClick={handleCreate}
                    disabled={creating || !form.agent_id}
                    className="h-8 text-xs gap-1.5"
                  >
                    <Play className="h-3 w-3" />
                    {creating ? "Creating…" : "Create schedule"}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-8 text-xs"
                    onClick={() => setShowForm(false)}
                  >
                    Cancel
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Schedule list */}
          {loading ? (
            <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-flow-brand border-t-transparent" />
              Loading schedules…
            </div>
          ) : schedules.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-12 text-center">
              <Calendar className="h-8 w-8 text-muted-foreground/30" />
              <p className="text-sm text-muted-foreground">No schedules yet.</p>
              <p className="text-xs text-muted-foreground/60">Schedules run an agent automatically on a cron expression.</p>
            </div>
          ) : (
            <div className="grid gap-2">
              {schedules.map((s) => (
                <div
                  key={s.id}
                  className={cn(
                    "flex items-start gap-4 rounded-xl border border-border/50 bg-card/60 px-4 py-3 transition-opacity",
                    !s.enabled && "opacity-50",
                  )}
                >
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted/50 mt-0.5">
                    <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium">{s.agent_name}</span>
                      <Badge variant="outline" className="font-mono text-[10px]">{s.cron_expr}</Badge>
                      {s.delivery_type === "webhook" && (
                        <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
                          <Webhook className="h-2.5 w-2.5" />
                          webhook
                        </span>
                      )}
                      <Badge variant={s.enabled ? "default" : "secondary"} className="text-[10px]">
                        {s.enabled ? "active" : "paused"}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground line-clamp-1">{s.prompt_template}</p>
                    {s.last_run_at && (
                      <p className="text-[11px] text-muted-foreground/60 flex items-center gap-1">
                        <Clock className="h-2.5 w-2.5" />
                        Last run {new Date(s.last_run_at).toLocaleString()}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-[11px]"
                      onClick={() => handleToggle(s.id, s.enabled)}
                    >
                      {s.enabled ? "Pause" : "Resume"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => handleDelete(s.id)}
                      title="Delete"
                    >
                      <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
