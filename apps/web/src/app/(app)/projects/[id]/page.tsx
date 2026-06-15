"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  BookOpen,
  CalendarClock,
  CheckCircle2,
  Download,
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
import { apiFetch, getApiBase } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const DIGEST_LABELS: Record<string, string> = {
  "digest.start":         "Starting digest…",
  "digest.fetch_done":    "Papers fetched",
  "digest.scoring":       "Scoring relevance…",
  "digest.filter_done":   "Filtering done",
  "digest.summarize_done":"Summaries ready",
  "digest.persist_done":  "Persisted to KG",
  "digest.complete":      "Complete",
}

function formatDigestPayload(payload: Record<string, unknown>): string {
  if (payload.count !== undefined) return `${payload.count} papers`
  if (payload.persisted !== undefined) return `${payload.persisted} ingested`
  return ""
}

type Project = {
  id: string;
  workspace_id: string;
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
  digest_run_id: string | null;
};

type Paper = {
  id: string;
  title: string;
  abstract: string | null;
  source_url: string | null;
  arxiv_id: string | null;
  authors: string[];
  categories: string[];
  relevance_score: number | null;
  tldr: string | null;
  status: string | null;
  obsidian_path: string | null;
  published_at: string | null;
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
  const setActiveTask = useStore((s) => s.setActiveTask);
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
  const [papers, setPapers] = useState<Paper[]>([]);
  const [expandedPaper, setExpandedPaper] = useState<string | null>(null);
  const [references, setReferences] = useState<{ name: string; title: string }[]>([]);
  const [refsFolder, setRefsFolder] = useState<string | null>(null);
  const [exportingRefs, setExportingRefs] = useState(false);
  const [exportRefsResult, setExportRefsResult] = useState<string | null>(null);

  async function loadReferences() {
    if (!id) return;
    try {
      const r = await apiFetch<{ folder: string; files: { name: string; title: string }[] }>(
        `/api/v1/projects/${id}/references`,
      );
      setReferences(r.files);
      setRefsFolder(r.folder);
    } catch {
      setReferences([]);
    }
  }

  async function exportReferences() {
    if (!id) return;
    setExportingRefs(true);
    setExportRefsResult(null);
    try {
      const r = await apiFetch<{ exported: number; skipped: number; folder: string }>(
        `/api/v1/projects/${id}/export-references`,
        { method: "POST", json: {} },
      );
      setExportRefsResult(`Exported ${r.exported} references${r.skipped ? ` (${r.skipped} skipped)` : ""}`);
      await loadReferences();
    } catch (e) {
      setExportRefsResult(`Error: ${String(e)}`);
    } finally {
      setExportingRefs(false);
    }
  }
  const [liveEvents, setLiveEvents] = useState<{ kind: string; payload: Record<string, unknown>; ts: number }[]>([]);
  const liveAbortRef = useRef<AbortController | null>(null);
  const [exportingRunId, setExportingRunId] = useState<string | null>(null);
  const [exportResults, setExportResults] = useState<Record<string, { exported: number; error?: string }>>({});

  async function load() {
    if (!id) return;
    setLoading(true);
    setRunsLoading(true);
    try {
      const [p, runsData, papersData] = await Promise.all([
        apiFetch<Project>(`/api/v1/projects/${id}`),
        apiFetch<{ runs: ProjectRun[] }>(`/api/v1/projects/${id}/runs`).catch(() => ({ runs: [] })),
        apiFetch<{ papers: Paper[] }>(`/api/v1/projects/${id}/papers`).catch(() => ({ papers: [] })),
      ]);
      setProject(p);
      setRuns(runsData.runs);
      setPapers(papersData.papers);
      void loadReferences();
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

  function startLiveStream(wsId: string) {
    const ctrl = new AbortController();
    liveAbortRef.current = ctrl;
    const token = getToken();
    const base = getApiBase();
    fetch(`${base}/api/v1/stream?workspace_id=${wsId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: ctrl.signal,
    }).then(async (res) => {
      if (!res.body) return;
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          try {
            const ev = JSON.parse(line.slice(5).trim()) as Record<string, unknown>;
            if (typeof ev.kind === "string" && ev.kind.startsWith("digest.")) {
              setLiveEvents(prev => [{ kind: ev.kind as string, payload: ev, ts: Date.now() }, ...prev]);
            }
          } catch { /* ignore parse errors */ }
        }
      }
    }).catch(() => { /* aborted or network error */ });
  }

  async function trigger() {
    if (!project) return;
    setLiveEvents([]);
    startLiveStream(project.workspace_id);
    setTriggering(true);
    setTriggerResult(null);
    setActiveTask({ type: 'research', label: 'Digest running…', href: `/projects/${project.id}` });
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
      liveAbortRef.current?.abort();
      setActiveTask(null);
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

  async function handleExportObsidian(run: ProjectRun) {
    if (!run.digest_run_id) return;
    setExportingRunId(run.id);
    try {
      const data = await apiFetch<{ exported: number }>(
        `/api/v1/digest/runs/${run.digest_run_id}/export-obsidian`,
        { method: "POST" },
      );
      setExportResults((prev) => ({ ...prev, [run.id]: { exported: data.exported } }));
    } catch (e) {
      setExportResults((prev) => ({ ...prev, [run.id]: { exported: 0, error: String(e) } }));
    } finally {
      setExportingRunId(null);
    }
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

        {(triggering || liveEvents.length > 0) && (
          <div className="rounded-[6px] border border-flow-800 bg-flow-950 p-3 font-mono text-xs space-y-1 animate-fade-in">
            <p className="text-[10px] uppercase tracking-widest text-flow-500 mb-2">Live</p>
            {triggering && liveEvents.length === 0 && (
              <p className="text-muted-foreground/60 animate-pulse">Starting…</p>
            )}
            {liveEvents.map((ev, i) => (
              <div key={i} className="flex items-center gap-2 text-flow-200">
                <span className="shrink-0 text-flow-violet">{DIGEST_LABELS[ev.kind] ?? ev.kind}</span>
                {formatDigestPayload(ev.payload) && (
                  <span className="text-muted-foreground/60">{formatDigestPayload(ev.payload)}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Research papers — full transparency into what was ingested */}
      <div className="space-y-3">
        <h2 className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60">
          <BookOpen className="h-3 w-3" />
          Research Papers
          {papers.length > 0 && (
            <span className="rounded-full bg-flow-violet/15 px-1.5 text-flow-violet">{papers.length}</span>
          )}
        </h2>

        {papers.length === 0 ? (
          <p className="rounded-[6px] border border-flow-800 p-4 text-center font-mono text-[11px] text-muted-foreground/40">
            No papers yet. Run the digest to fetch and ingest research.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {papers.map((paper) => {
              const score = paper.relevance_score ?? 0;
              const scoreColor =
                score >= 0.7 ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/5"
                : score >= 0.4 ? "text-amber-400 border-amber-500/30 bg-amber-500/5"
                : "text-flow-500 border-flow-700 bg-flow-900";
              const open = expandedPaper === paper.id;
              const link = paper.source_url || (paper.arxiv_id ? `https://arxiv.org/abs/${paper.arxiv_id}` : null);
              return (
                <div
                  key={paper.id}
                  className="flex flex-col gap-2 rounded-[8px] border border-flow-800 bg-flow-900/30 p-3.5 transition-colors hover:border-flow-violet/40"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className={cn("shrink-0 rounded border px-1.5 py-0.5 font-mono text-[10px] tabular-nums", scoreColor)}>
                      {(score * 100).toFixed(0)}
                    </span>
                    {paper.obsidian_path && (
                      <span className="font-mono text-[9px] text-emerald-400/70" title="Exported to Obsidian">
                        ✓ obsidian
                      </span>
                    )}
                  </div>
                  {link ? (
                    <a href={link} target="_blank" rel="noreferrer" className="text-sm font-medium leading-snug text-foreground hover:text-flow-violet transition-colors line-clamp-3">
                      {paper.title}
                    </a>
                  ) : (
                    <p className="text-sm font-medium leading-snug text-foreground line-clamp-3">{paper.title}</p>
                  )}
                  {paper.tldr && (
                    <p className={cn("text-[12px] leading-relaxed text-muted-foreground", !open && "line-clamp-4")}>
                      {paper.tldr}
                    </p>
                  )}
                  <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-1">
                    {paper.categories.slice(0, 3).map((c) => (
                      <span key={c} className="rounded border border-flow-700/50 px-1.5 py-0.5 font-mono text-[9px] text-flow-300">
                        {c}
                      </span>
                    ))}
                    {paper.abstract && (
                      <button
                        type="button"
                        onClick={() => setExpandedPaper(open ? null : paper.id)}
                        className="font-mono text-[9px] text-flow-violet hover:underline"
                      >
                        {open ? "less" : "abstract"}
                      </button>
                    )}
                  </div>
                  {open && paper.abstract && (
                    <p className="rounded bg-flow-950/50 p-2 text-[11px] leading-relaxed text-muted-foreground/80">
                      {paper.abstract}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Obsidian references — export + existing notes in the thesis library */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60">
            <BookOpen className="h-3 w-3" />
            Obsidian References
            {references.length > 0 && (
              <span className="rounded-full bg-emerald-500/15 px-1.5 text-emerald-400">{references.length}</span>
            )}
          </h2>
          <Button
            size="sm"
            variant="outline"
            disabled={exportingRefs || papers.length === 0}
            onClick={() => void exportReferences()}
            className="gap-1.5 font-mono text-[10px]"
            title="Write all papers as reference notes into your Obsidian thesis folder"
          >
            {exportingRefs ? <Loader2 className="h-3 w-3 animate-spin" /> : <Download className="h-3 w-3" />}
            Export {papers.length} to Obsidian
          </Button>
        </div>

        {refsFolder && (
          <p className="font-mono text-[10px] text-muted-foreground/40">vault/{refsFolder}</p>
        )}
        {exportRefsResult && (
          <p className={cn("font-mono text-[11px]", exportRefsResult.startsWith("Error") ? "text-destructive" : "text-emerald-400")}>
            {exportRefsResult}
          </p>
        )}

        {references.length === 0 ? (
          <p className="rounded-[6px] border border-flow-800 p-4 text-center font-mono text-[11px] text-muted-foreground/40">
            No reference notes yet in this folder. Export papers above to populate it.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {references.map((ref) => (
              <div key={ref.name} className="flex items-center gap-2 rounded-[6px] border border-flow-800 bg-flow-900/20 p-2.5">
                <BookOpen className="h-3 w-3 shrink-0 text-emerald-400/60" />
                <span className="truncate text-[12px] text-foreground/80" title={ref.title}>{ref.title}</span>
              </div>
            ))}
          </div>
        )}
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
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <span className="font-mono text-[10px] text-muted-foreground/40">
                    {run.kg_nodes_before} → {run.kg_nodes_after}
                  </span>
                  {run.digest_run_id && (
                    <button
                      disabled={exportingRunId === run.id}
                      onClick={() => void handleExportObsidian(run)}
                      className={cn(
                        "flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[9px] transition-colors",
                        exportingRunId === run.id
                          ? "cursor-wait border-flow-800 text-flow-600"
                          : exportResults[run.id]?.error
                          ? "border-red-500/30 text-red-400"
                          : exportResults[run.id]
                          ? "border-emerald-500/30 text-emerald-400"
                          : "border-flow-700 text-flow-400 hover:border-flow-500 hover:text-flow-200",
                      )}
                      title="Export papers from this run to your Obsidian vault"
                    >
                      {exportingRunId === run.id ? (
                        <Loader2 className="h-2.5 w-2.5 animate-spin" />
                      ) : (
                        <Download className="h-2.5 w-2.5" />
                      )}
                      {exportResults[run.id]?.error
                        ? "Error"
                        : exportResults[run.id]
                        ? `✓ ${exportResults[run.id].exported} notes`
                        : "Obsidian"}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
