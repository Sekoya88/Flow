"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  BookOpen,
  CalendarClock,
  Loader2,
  Play,
  Plus,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { apiFetch } from "@/lib/api";
import { useStore } from "@/lib/store";
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

function cronLabel(cron: string): string {
  const map: Record<string, string> = {
    "0 9 * * 1": "Weekly · Mon 9am",
    "0 9 * * *": "Daily · 9am",
    "0 9 1 * *": "Monthly · 1st",
  };
  return map[cron] ?? cron;
}

export default function ProjectsPage() {
  const workspaceId = useStore((s) => s.workspaces[0]?.id ?? null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: "",
    goal: "",
    arxiv_categories: "cs.AI, cs.LG",
    cadence_cron: "0 9 * * 1",
    kg_namespace: "",
  });
  const [creating, setCreating] = useState(false);
  const [triggering, setTriggering] = useState<string | null>(null);

  async function load() {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const d = await apiFetch<{ projects: Project[] }>(
        `/api/v1/workspaces/${workspaceId}/projects`,
      );
      setProjects(d.projects ?? []);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [workspaceId]);

  async function create() {
    if (!workspaceId || !form.name.trim()) return;
    setCreating(true);
    try {
      await apiFetch("/api/v1/workspaces/" + workspaceId + "/projects", {
        method: "POST",
        json: {
          name: form.name.trim(),
          goal: form.goal.trim(),
          arxiv_categories: form.arxiv_categories
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
          cadence_cron: form.cadence_cron || "0 9 * * 1",
          kg_namespace: form.kg_namespace.trim(),
        },
      });
      setShowCreate(false);
      setForm({ name: "", goal: "", arxiv_categories: "cs.AI, cs.LG", cadence_cron: "0 9 * * 1", kg_namespace: "" });
      await load();
    } finally {
      setCreating(false);
    }
  }

  async function trigger(id: string) {
    setTriggering(id);
    try {
      await apiFetch(`/api/v1/projects/${id}/trigger`, { method: "POST" });
      await load();
    } finally {
      setTriggering(null);
    }
  }

  async function remove(id: string) {
    await apiFetch(`/api/v1/projects/${id}`, { method: "DELETE" });
    setProjects((p) => p.filter((x) => x.id !== id));
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-8 px-4 pb-12 pt-6 animate-fade-in">
      <header className="space-y-2">
        <div className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-flow-violet" />
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-flow-violet/80">
            Research Projects
          </span>
        </div>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-foreground">Projects</h1>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground leading-relaxed">
              Long-running research accumulators. Each project watches arxiv categories and URLs on a schedule, ingesting papers into the KG.
            </p>
          </div>
          <Button
            onClick={() => setShowCreate(true)}
            className="shrink-0 gap-1.5 bg-flow-violet text-white hover:bg-flow-violet/80"
          >
            <Plus className="h-3.5 w-3.5" />
            New Project
          </Button>
        </div>
      </header>

      {showCreate && (
        <div className="rounded-[8px] border border-flow-violet/30 bg-flow-900/60 p-5 space-y-4">
          <h2 className="font-mono text-xs font-semibold text-flow-200">New Research Project</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">Name</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="AI Safety Weekly"
                className="font-mono text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">Cadence (cron)</Label>
              <Input
                value={form.cadence_cron}
                onChange={(e) => setForm((f) => ({ ...f, cadence_cron: e.target.value }))}
                placeholder="0 9 * * 1"
                className="font-mono text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">Arxiv Categories</Label>
              <Input
                value={form.arxiv_categories}
                onChange={(e) => setForm((f) => ({ ...f, arxiv_categories: e.target.value }))}
                placeholder="cs.AI, cs.LG, cs.CL"
                className="font-mono text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">KG Namespace</Label>
              <Input
                value={form.kg_namespace}
                onChange={(e) => setForm((f) => ({ ...f, kg_namespace: e.target.value }))}
                placeholder="ai-safety"
                className="font-mono text-xs"
              />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">Research Goal (optional)</Label>
              <Textarea
                value={form.goal}
                onChange={(e) => setForm((f) => ({ ...f, goal: e.target.value }))}
                rows={2}
                placeholder="Track advances in interpretability and alignment..."
                className="resize-none font-mono text-xs"
              />
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <Button variant="ghost" size="sm" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button
              size="sm"
              disabled={creating || !form.name.trim()}
              onClick={() => void create()}
              className="gap-1.5 bg-flow-violet text-white hover:bg-flow-violet/80"
            >
              {creating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
              Create
            </Button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading projects…
        </div>
      ) : projects.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          tone="brand"
          title="No research projects yet"
          description="Create a project to start accumulating papers from arxiv categories into your knowledge graph on a schedule."
          action={
            <Button
              onClick={() => setShowCreate(true)}
              className="gap-1.5 bg-flow-violet text-white hover:bg-flow-violet/80"
            >
              <Plus className="h-3.5 w-3.5" />
              New Project
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {projects.map((p) => (
            <div
              key={p.id}
              className={cn(
                "flow-card group rounded-[10px] border p-5 space-y-3 transition-all duration-200",
                p.enabled
                  ? "border-flow-800 hover:border-flow-violet/40"
                  : "border-flow-800/50 opacity-60",
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <Link
                    href={`/projects/${p.id}`}
                    className="font-mono text-sm font-semibold text-flow-50 hover:text-flow-violet transition-colors"
                  >
                    {p.name}
                  </Link>
                  {p.goal && (
                    <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground/70">
                      {p.goal}
                    </p>
                  )}
                </div>
                <Badge
                  variant="outline"
                  className={cn(
                    "shrink-0 font-mono text-[9px]",
                    p.enabled
                      ? "border-emerald-500/30 text-emerald-400"
                      : "border-flow-700 text-flow-600",
                  )}
                >
                  {p.enabled ? "active" : "paused"}
                </Badge>
              </div>

              <div className="flex flex-wrap gap-1">
                {p.arxiv_categories.slice(0, 4).map((cat) => (
                  <span
                    key={cat}
                    className="rounded-[4px] border border-flow-700/50 bg-flow-900 px-1.5 py-0.5 font-mono text-[9px] text-flow-400"
                  >
                    {cat}
                  </span>
                ))}
                {p.arxiv_categories.length > 4 && (
                  <span className="font-mono text-[9px] text-flow-600">
                    +{p.arxiv_categories.length - 4}
                  </span>
                )}
              </div>

              <div className="flex items-center justify-between text-[10px] text-flow-600">
                <span className="flex items-center gap-1">
                  <CalendarClock className="h-3 w-3" />
                  {cronLabel(p.cadence_cron)}
                </span>
                {p.last_run_at && (
                  <span>last run {new Date(p.last_run_at).toLocaleDateString()}</span>
                )}
              </div>

              <div className="flex items-center gap-2 pt-1 border-t border-flow-800">
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={triggering === p.id}
                  onClick={() => void trigger(p.id)}
                  className="h-7 gap-1 px-2 font-mono text-[10px] text-flow-400 hover:text-flow-200"
                >
                  {triggering === p.id ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Play className="h-3 w-3" />
                  )}
                  Run now
                </Button>
                <Link
                  href={`/projects/${p.id}`}
                  className="ml-auto font-mono text-[10px] text-flow-500 hover:text-flow-200 transition-colors"
                >
                  Details →
                </Link>
                <button
                  type="button"
                  onClick={() => void remove(p.id)}
                  className="text-flow-700 hover:text-destructive transition-colors"
                  aria-label="Delete project"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
