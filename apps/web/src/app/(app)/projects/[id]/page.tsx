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
  Loader2,
  Play,
  Tag,
  ToggleLeft,
  ToggleRight,
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

  async function load() {
    if (!id) return;
    setLoading(true);
    try {
      const p = await apiFetch<Project>(`/api/v1/projects/${id}`);
      setProject(p);
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
    </div>
  );
}
