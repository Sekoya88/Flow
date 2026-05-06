"use client";

import { useEffect, useState } from "react";
import { Clock, Plus, Trash2, ToggleLeft, ToggleRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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

export default function SchedulesPage() {
  const workspaceId = useStore((s) => s.workspaceId);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    agent_id: "",
    cron_expr: "0 8 * * *",
    prompt_template: "Summarize the latest AI research papers from today.",
    delivery_type: "none",
    delivery_target: "",
  });

  useEffect(() => {
    if (!workspaceId) return;
    Promise.all([
      apiFetch<{ schedules: Schedule[] }>(`/api/v1/schedules?workspace_id=${workspaceId}`),
      apiFetch<{ agents: AgentRow[] }>(`/api/v1/agents?workspace_id=${workspaceId}`),
    ])
      .then(([sData, aData]) => {
        setSchedules(sData.schedules ?? []);
        setAgents(aData.agents ?? []);
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
      await apiFetch(`/api/v1/schedules/${id}?workspace_id=${workspaceId}`, {
        method: "DELETE",
      });
      setSchedules((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      console.warn("delete failed:", err);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <FlowPageHeader title="Schedules" />
      <div className="flex-1 overflow-auto p-6 space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">New Schedule</CardTitle>
            <CardDescription>Run an agent automatically on a cron schedule.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Agent</Label>
                <Select
                  value={form.agent_id}
                  onValueChange={(v) => setForm((f) => ({ ...f, agent_id: v }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select agent" />
                  </SelectTrigger>
                  <SelectContent>
                    {agents.map((a) => (
                      <SelectItem key={a.id} value={a.id}>
                        {a.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Cron expression</Label>
                <Input
                  value={form.cron_expr}
                  onChange={(e) => setForm((f) => ({ ...f, cron_expr: e.target.value }))}
                  placeholder="0 8 * * *"
                  className="font-mono"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Prompt template</Label>
              <Textarea
                value={form.prompt_template}
                onChange={(e) => setForm((f) => ({ ...f, prompt_template: e.target.value }))}
                rows={3}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Delivery</Label>
                <Select
                  value={form.delivery_type}
                  onValueChange={(v) => setForm((f) => ({ ...f, delivery_type: v }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    <SelectItem value="webhook">Webhook</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {form.delivery_type === "webhook" && (
                <div className="space-y-1.5">
                  <Label>Webhook URL</Label>
                  <Input
                    value={form.delivery_target}
                    onChange={(e) => setForm((f) => ({ ...f, delivery_target: e.target.value }))}
                    placeholder="https://hooks.example.com/..."
                  />
                </div>
              )}
            </div>
            <Button onClick={handleCreate} disabled={creating || !form.agent_id} className="gap-2">
              <Plus className="h-4 w-4" />
              Create schedule
            </Button>
          </CardContent>
        </Card>

        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : schedules.length === 0 ? (
          <p className="text-sm text-muted-foreground">No schedules yet. Create one above.</p>
        ) : (
          <div className="space-y-3">
            {schedules.map((s) => (
              <Card key={s.id} className={cn(!s.enabled && "opacity-60")}>
                <CardContent className="flex items-start justify-between gap-4 py-4">
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm">{s.agent_name}</span>
                      <Badge variant="outline" className="font-mono text-xs">
                        {s.cron_expr}
                      </Badge>
                      {s.delivery_type === "webhook" && (
                        <Badge variant="secondary" className="text-xs">
                          webhook
                        </Badge>
                      )}
                      <Badge
                        variant={s.enabled ? "default" : "secondary"}
                        className="text-xs"
                      >
                        {s.enabled ? "active" : "paused"}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground line-clamp-2">
                      {s.prompt_template}
                    </p>
                    {s.last_run_at && (
                      <p className="text-[11px] text-muted-foreground flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        Last run {new Date(s.last_run_at).toLocaleString()}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleToggle(s.id, s.enabled)}
                      title={s.enabled ? "Pause" : "Resume"}
                    >
                      {s.enabled ? (
                        <ToggleRight className="h-4 w-4 text-emerald-500" />
                      ) : (
                        <ToggleLeft className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(s.id)}
                      title="Delete"
                    >
                      <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
