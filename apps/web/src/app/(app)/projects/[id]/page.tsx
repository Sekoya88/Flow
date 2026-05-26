"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  BookOpen,
  CalendarClock,
  CheckCircle2,
  Layers,
  Loader2,
  Play,
  Tag,
  ToggleLeft,
  ToggleRight,
  TrendingUp,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

type Project = {
  id: string;
  name: string;
  goal: string;
  arxiv_categories: string[];
  source_urls: string[];
  cadence_cron: string;
  kg_namespace: string;
  enabled: boolean;
  created_at: string;
  last_run_at: string | null;
};

type ProjectRun = {
  id: string;
  papers_processed: number;
  kg_nodes_before: number;
  kg_nodes_after: number;
  kg_nodes_added: number;
  status: string;
  error_message: string | null;
  created_at: string;
};

// ── Inline SVG sparkline ──────────────────────────────────────────────────────
function RunSparkline({ runs }: { runs: ProjectRun[] }) {
  const data = [...runs].reverse().map((r) => r.papers_processed);
  if (data.length < 2) return <span className="text-[10px] text-muted-foreground/40 italic">no history</span>;
  const W = 120; const H = 28; const pad = 3;
  const w = W - pad * 2; const h = H - pad * 2;
  const max = Math.max(...data, 1);
  const pts = data
    .map((v, i) => `${(pad + (i / (data.length - 1)) * w).toFixed(1)},${(pad + (1 - v / max) * h).toFixed(1)}`)
    .join(" ");
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="overflow-visible">
      <polyline points={pts} fill="none" stroke="#a78bfa" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      {data.map((v, i) => {
        const cx = pad + (i / (data.length - 1)) * w;
        const cy = pad + (1 - v / max) * h;
        return <circle key={i} cx={cx} cy={cy} r="2.5" fill="#a78bfa" />;
      })}
    </svg>
  );
}

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ name: "", goal: "", arxiv_categories: "", cadence_cron: "", kg_namespace: "" });
  const [saving, setSaving] = useState(false);
  const [runs, setRuns] = useState<ProjectRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);

  async function load() {
    if (!id) return;
    setLoading(true);
    setRunsLoading(true);
    try {
      const [p, runsData] = await Promise.all([
        apiFetch<Project>(`/api/v1/projects/${id}`),
        apiFetch<{ runs: ProjectRun[] }>(`/api/v1/projects/${id}/runs`).catch(() => ({ runs: [] })),
      ]);
      setProject(p);
      setRuns(runsData.runs);
      setForm({
        name: p.name,
        goal: p.goal,
        arxiv_categories: p.arxiv_categories.join(", "),
        cadence_cron: p.cadence_cron,
        kg_namespace: p.kg_namespace,
      });
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
      setRunsLoading(false);
    }
  }

  useEffect(() => { void load(); }, [id]);

  async function trigger() {
    if (!project) return;
    setTriggering(true);
    setTriggerResult(null);
    try {
      const r = await apiFetch<{ status: string; papers_processed: number }>(
        `/api/v1/projects/${project.id}/trigger`,
        { method: "POST" },
      );
      setTriggerResult(`Done — ${r.papers_processed} papers ingested`);
      await load();
    } catch (e) {
      setTriggerResult(`Error: ${String(e)}`);
    } finally {
      setTriggering(false);
    }
  }

  async function save() {
    if (!project) return;
    setSaving(true);
    try {
      const updated = await apiFetch<Project>(`/api/v1/projects/${project.id}`, {
        method: "PATCH",
        json: {
          name: form.name.trim(),
          goal: form.goal.trim(),
          arxiv_categories: form.arxiv_categories.split(",").map((s) => s.trim()).filter(Boolean),
          cadence_cron: form.cadence_cron.trim(),
          kg_namespace: form.kg_namespace.trim(),
        },
      });
      setProject(updated);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  async function toggleEnabled() {
    if (!project) return;
    const updated = await apiFetch<Project>(`/api/v1/projects/${project.id}`, {
      method: "PATCH",
      json: { enabled: !project.enabled },
    });
    setProject(updated);
  }

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-flow-500" />
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="flex h-[60vh] flex-col items-center justify-center gap-3">
        <AlertCircle className="h-6 w-6 text-destructive" />
        <p className="font-mono text-xs text-flow-500">{error ?? "Not found"}</p>
        <Link href="/projects" className="font-mono text-[11px] text-flow-violet hover:underline">
          ← Back to Projects
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-8 px-4 pb-12 pt-6 animate-fade-in">
      {/* Back */}
      <Link
        href="/projects"
        className="inline-flex items-center gap-1.5 font-mono text-[11px] text-flow-500 hover:text-flow-200 transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Projects
      </Link>

      {/* Header */}
      <header className="space-y-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-flow-violet" />
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">{project.name}</h1>
            <Badge
              variant="outline"
              className={cn(
                "font-mono text-[9px]",
                project.enabled
                  ? "border-emerald-500/30 text-emerald-400"
                  : "border-flow-700 text-flow-600",
              )}
            >
              {project.enabled ? "active" : "paused"}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void toggleEnabled()}
              className="flex items-center gap-1.5 font-mono text-[10px] text-flow-500 hover:text-flow-200 transition-colors"
              title={project.enabled ? "Pause project" : "Resume project"}
            >
              {project.enabled ? (
                <ToggleRight className="h-4 w-4 text-emerald-400" />
              ) : (
                <ToggleLeft className="h-4 w-4 text-flow-600" />
              )}
              {project.enabled ? "Pause" : "Resume"}
            </button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setEditing((e) => !e)}
              className="font-mono text-[10px]"
            >
              {editing ? "Cancel" : "Edit"}
            </Button>
          </div>
        </div>
        {project.goal && !editing && (
          <p className="text-sm text-muted-foreground leading-relaxed">{project.goal}</p>
        )}
      </header>

      {editing ? (
        <div className="rounded-[8px] border border-flow-violet/30 bg-flow-900/60 p-5 space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">Name</Label>
              <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} className="font-mono text-xs" />
            </div>
            <div className="space-y-1.5">
              <Label className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">Cadence (cron)</Label>
              <Input value={form.cadence_cron} onChange={(e) => setForm((f) => ({ ...f, cadence_cron: e.target.value }))} className="font-mono text-xs" />
            </div>
            <div className="space-y-1.5">
              <Label className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">Arxiv Categories</Label>
              <Input value={form.arxiv_categories} onChange={(e) => setForm((f) => ({ ...f, arxiv_categories: e.target.value }))} className="font-mono text-xs" />
            </div>
            <div className="space-y-1.5">
              <Label className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">KG Namespace</Label>
              <Input value={form.kg_namespace} onChange={(e) => setForm((f) => ({ ...f, kg_namespace: e.target.value }))} className="font-mono text-xs" />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">Goal</Label>
              <Textarea value={form.goal} onChange={(e) => setForm((f) => ({ ...f, goal: e.target.value }))} rows={2} className="resize-none font-mono text-xs" />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>Cancel</Button>
            <Button size="sm" disabled={saving} onClick={() => void save()} className="gap-1.5 bg-flow-violet text-white hover:bg-flow-violet/80">
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
              Save
            </Button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {/* Categories */}
          <div className="flow-card rounded-[8px] border border-flow-800 p-4 space-y-2">
            <p className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60">
              <Tag className="h-3 w-3" />
              Arxiv Categories
            </p>
            <div className="flex flex-wrap gap-1">
              {project.arxiv_categories.length > 0 ? project.arxiv_categories.map((cat) => (
                <span key={cat} className="rounded-[4px] border border-flow-700/50 bg-flow-900 px-2 py-0.5 font-mono text-[10px] text-flow-300">
                  {cat}
                </span>
              )) : <span className="text-[11px] text-muted-foreground/40">none</span>}
            </div>
          </div>

          {/* Schedule */}
          <div className="flow-card rounded-[8px] border border-flow-800 p-4 space-y-2">
            <p className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60">
              <CalendarClock className="h-3 w-3" />
              Schedule
            </p>
            <p className="font-mono text-sm text-flow-200">{project.cadence_cron}</p>
            {project.last_run_at && (
              <p className="font-mono text-[10px] text-flow-600">
                last run: {new Date(project.last_run_at).toLocaleString()}
              </p>
            )}
          </div>

          {/* Source URLs */}
          {project.source_urls.length > 0 && (
            <div className="flow-card rounded-[8px] border border-flow-800 p-4 space-y-2 sm:col-span-2">
              <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60">Source URLs</p>
              <ul className="space-y-1">
                {project.source_urls.map((url) => (
                  <li key={url}>
                    <a href={url} target="_blank" rel="noreferrer" className="font-mono text-[11px] text-flow-violet hover:underline break-all">
                      {url}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* KG namespace */}
          {project.kg_namespace && (
            <div className="flow-card rounded-[8px] border border-flow-800 p-4 space-y-1">
              <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60">KG Namespace</p>
              <p className="font-mono text-sm text-flow-200">{project.kg_namespace}</p>
            </div>
          )}
        </div>
      )}

      {/* Manual trigger */}
      <div className="rounded-[8px] border border-flow-800 bg-flow-900/40 p-5 space-y-3">
        <h2 className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60">Manual Run</h2>
        <p className="text-[11px] text-muted-foreground/70">
          Run the research digest immediately for this project. Papers will be fetched, filtered, summarized, and ingested into the KG.
        </p>
        <div className="flex items-center gap-3">
          <Button
            disabled={triggering}
            onClick={() => void trigger()}
            className="gap-1.5 bg-flow-violet text-white hover:bg-flow-violet/80"
          >
            {triggering ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Running…
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5" />
                Run Now
              </>
            )}
          </Button>
          {triggerResult && (
            <p
              className={cn(
                "font-mono text-[11px] animate-fade-in",
                triggerResult.startsWith("Done") ? "text-emerald-400" : "text-destructive",
              )}
            >
              {triggerResult}
            </p>
          )}
        </div>
      </div>

      {/* Run history timeline */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60">
            <TrendingUp className="h-3 w-3" />
            Run History
          </h2>
          {runs.length >= 2 && (
            <RunSparkline runs={runs} />
          )}
        </div>

        {runsLoading && (
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground/50">
            <Loader2 className="h-3 w-3 animate-spin" />
            Loading…
          </div>
        )}

        {!runsLoading && runs.length === 0 && (
          <p className="rounded-[6px] border border-flow-800 p-4 text-center font-mono text-[11px] text-muted-foreground/40">
            No runs yet. Use &quot;Run Now&quot; above to start.
          </p>
        )}

        {!runsLoading && runs.length > 0 && (
          <div className="space-y-2">
            {runs.slice(0, 10).map((run) => (
              <div
                key={run.id}
                className={cn(
                  "flex items-start justify-between gap-4 rounded-[6px] border p-3",
                  run.status === "completed"
                    ? "border-flow-800 bg-flow-900/30"
                    : "border-destructive/20 bg-destructive/5",
                )}
              >
                <div className="flex items-start gap-2.5 min-w-0">
                  {run.status === "completed" ? (
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0 mt-0.5 text-emerald-500" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5 shrink-0 mt-0.5 text-destructive" />
                  )}
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-medium text-foreground">
                        {run.papers_processed} paper{run.papers_processed !== 1 ? "s" : ""} ingested
                      </span>
                      {run.kg_nodes_added > 0 && (
                        <span className="flex items-center gap-0.5 font-mono text-[10px] text-flow-violet">
                          <Layers className="h-2.5 w-2.5" />
                          +{run.kg_nodes_added} KG nodes
                        </span>
                      )}
                    </div>
                    {run.error_message && (
                      <p className="font-mono text-[10px] text-destructive truncate max-w-xs">
                        {run.error_message}
                      </p>
                    )}
                    <p className="font-mono text-[10px] text-muted-foreground/50">
                      {new Date(run.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="shrink-0 text-right font-mono text-[10px] text-muted-foreground/40">
                  {run.kg_nodes_before} → {run.kg_nodes_after}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
