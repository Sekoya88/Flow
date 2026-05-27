"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  BookOpen,
  BookX,
  BrainCircuit,
  CheckCircle2,
  Download,
  ExternalLink,
  Loader2,
  Play,
  Settings2,
  Sparkles,
  Terminal,
  Trash2,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";

type Paper = {
  id: string;
  title: string;
  abstract: string | null;
  source_url: string | null;
  arxiv_id: string | null;
  authors: string[];
  categories: string[];
  relevance_score: number;
  tldr: string | null;
  key_insights: string | null;
  status: "unread" | "read" | "archived";
  published_at: string | null;
  digested_at: string;
};

type DigestConfig = {
  workspace_id: string;
  enabled: boolean;
  schedule_hour: number;
  min_relevance_score: number;
  arxiv_categories: string[];
  custom_sources: string[];
  user_interests: string;
  obsidian_mode: string;
  obsidian_vault_path: string | null;
};

type KnowledgeItem = { id: string; title: string; tldr: string | null };
type KnowledgePanel = { available: boolean; count: number; papers: KnowledgeItem[] };

const ARXIV_CHIPS = [
  { code: "cs.AI",   label: "AI" },
  { code: "cs.LG",   label: "ML" },
  { code: "cs.CL",   label: "NLP" },
  { code: "cs.CV",   label: "Vision" },
  { code: "cs.RO",   label: "Robotics" },
  { code: "cs.CR",   label: "Security" },
  { code: "cs.SE",   label: "Software Eng." },
  { code: "stat.ML", label: "Stat ML" },
  { code: "q-bio",   label: "Bio" },
  { code: "math.OC", label: "Optimization" },
];

type SynthesisResult = {
  topics: string[];
  methods: string[];
  datasets: string[];
  key_findings: string;
  open_questions: string[];
  synthesis_md: string;
  paper_count: number;
};

type ProgressEvent = {
  id: string;
  kind: string;
  ts: number;
  payload: Record<string, unknown>;
};

// ── Event kind display config ─────────────────────────────────────────

const DIGEST_EVENT_CONFIG: Record<string, {
  icon: React.FC<{ className?: string }>;
  color: string;
  label: string;
  detail?: (p: Record<string, unknown>) => string;
}> = {
  "digest.start":         { icon: Play,         color: "text-violet-400", label: "Digest started" },
  "digest.fetch_done":    { icon: BookOpen,      color: "text-sky-400",    label: "Papers fetched",    detail: (p) => `${p.count} papers` },
  "digest.scoring":       { icon: Zap,           color: "text-amber-400",  label: "Scoring relevance", detail: (p) => `${p.count} papers` },
  "digest.filter_done":   { icon: Zap,           color: "text-amber-400",  label: "Filtered",          detail: (p) => `${p.kept} relevant / ${p.total} total` },
  "digest.summarize_done":{ icon: Sparkles,       color: "text-violet-400", label: "Summarized",        detail: (p) => `${p.count} papers` },
  "digest.persist_done":  { icon: CheckCircle2,  color: "text-emerald-400",label: "Saved to DB",       detail: (p) => `${p.persisted} papers` },
  "digest.complete":      { icon: CheckCircle2,  color: "text-emerald-400",label: "Complete",          detail: (p) => `${p.persisted} new · ${p.filtered} filtered · ${p.fetched} fetched` },
};

// ── Live digest progress panel ────────────────────────────────────────

function DigestProgress({
  wsId,
  onComplete,
}: {
  wsId: string;
  onComplete: () => void;
}) {
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [done, setDone] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!wsId) return;
    const ctrl = new AbortController();
    const apiBase = (process.env.NEXT_PUBLIC_FLOW_API_URL ?? "").replace(/\/$/, "");
    const token = getToken();

    (async () => {
      try {
        const res = await fetch(`${apiBase}/api/v1/stream?workspace_id=${wsId}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: ctrl.signal,
        });
        if (!res.ok || !res.body) return;
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (true) {
          const { done: streamDone, value } = await reader.read();
          if (streamDone) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() ?? "";
          for (const line of lines) {
            if (!line.startsWith("data:")) continue;
            try {
              const parsed = JSON.parse(line.slice(5).trim()) as Record<string, unknown>;
              const kind = (parsed.kind as string) ?? "unknown";
              setEvents((prev) => [
                ...prev,
                { id: `${Date.now()}-${Math.random()}`, kind, ts: Date.now(), payload: parsed },
              ]);
              if (kind === "digest.complete") {
                setDone(true);
                ctrl.abort();
                onComplete();
              }
            } catch { /* malformed */ }
          }
        }
      } catch (e) {
        if ((e as Error)?.name !== "AbortError") {
          // stream error — silently ignore, papers will reload on timeout
        }
      }
    })();

    return () => ctrl.abort();
  }, [wsId, onComplete]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  return (
    <div className="rounded border border-flow-800 bg-flow-950/80 overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-flow-800 bg-flow-900/40">
        <Terminal className="h-3 w-3 text-flow-500" />
        <span className="font-mono text-[10px] uppercase tracking-widest text-flow-500">Live progress</span>
        {!done && <Loader2 className="h-3 w-3 animate-spin text-flow-500 ml-auto" />}
        {done && <CheckCircle2 className="h-3 w-3 text-emerald-400 ml-auto" />}
      </div>
      <div className="max-h-48 overflow-y-auto py-1">
        {events.length === 0 && (
          <div className="px-3 py-2 font-mono text-[11px] text-flow-600">
            Connecting to stream…
          </div>
        )}
        {events.map((ev) => {
          const cfg = DIGEST_EVENT_CONFIG[ev.kind] ?? { icon: Terminal, color: "text-flow-500", label: ev.kind };
          const Icon = cfg.icon;
          const detail = cfg.detail?.(ev.payload) ?? "";
          const ts = new Date(ev.ts).toLocaleTimeString(undefined, {
            hour: "2-digit", minute: "2-digit", second: "2-digit",
          });
          return (
            <div key={ev.id} className="flex items-center gap-2.5 px-3 py-1">
              <span className="font-mono text-[10px] text-flow-700 shrink-0 w-[56px]">{ts}</span>
              <Icon className={cn("h-3 w-3 shrink-0", cfg.color)} />
              <span className={cn("font-mono text-[11px] font-semibold shrink-0", cfg.color)}>{cfg.label}</span>
              {detail && <span className="font-mono text-[11px] text-flow-500">{detail}</span>}
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ── Paper card ────────────────────────────────────────────────────────

function PaperCard({
  paper,
  onStatusChange,
  onSummarize,
  onDelete,
  onDeleteFromVault,
  summarizing,
  selected,
  onToggleSelect,
}: {
  paper: Paper;
  onStatusChange: (id: string, status: string) => void;
  onSummarize: (id: string) => void;
  onDelete: (id: string) => void;
  onDeleteFromVault: (id: string) => void;
  summarizing: boolean;
  selected: boolean;
  onToggleSelect: (id: string) => void;
}) {
  const scoreColor =
    paper.relevance_score >= 0.8
      ? "text-emerald-400"
      : paper.relevance_score >= 0.6
        ? "text-amber-400"
        : "text-flow-500";

  return (
    <Card
      className={cn(
        "border-flow-800 bg-flow-900/50 transition-opacity",
        paper.status === "archived" && "opacity-40",
      )}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onToggleSelect(paper.id)}
            className="mt-0.5 h-3.5 w-3.5 shrink-0 cursor-pointer accent-violet-500"
          />
          <div className="min-w-0 flex-1">
            <CardTitle className="line-clamp-2 text-sm font-semibold leading-snug">
              {paper.title}
            </CardTitle>
            {paper.authors.length > 0 && (
              <CardDescription className="mt-0.5 truncate font-mono text-[10px]">
                {paper.authors.slice(0, 3).join(", ")}
                {paper.authors.length > 3 && " +more"}
              </CardDescription>
            )}
          </div>
          <span className={cn("shrink-0 font-mono text-[11px] font-bold", scoreColor)}>
            {(paper.relevance_score * 100).toFixed(0)}%
          </span>
        </div>
        <div className="mt-1 flex flex-wrap gap-1">
          {paper.categories.slice(0, 3).map((c) => (
            <Badge key={c} variant="outline" className="h-4 px-1.5 font-mono text-[9px]">
              {c}
            </Badge>
          ))}
        </div>
      </CardHeader>
      <CardContent className="space-y-2 pt-0">
        {paper.tldr && (
          <p className="rounded-[6px] bg-flow-800/60 px-3 py-2 text-xs leading-relaxed text-flow-300">
            {paper.tldr}
          </p>
        )}
        {!paper.tldr && paper.abstract && (
          <p className="line-clamp-3 text-xs leading-relaxed text-flow-400">
            {paper.abstract}
          </p>
        )}
        <div className="flex items-center justify-between pt-1">
          <div className="flex gap-1.5">
            {paper.source_url && (
              <a
                href={paper.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 font-mono text-[10px] text-flow-500 hover:text-flow-300 transition-colors"
              >
                <ExternalLink className="h-3 w-3" />
                Paper
              </a>
            )}
            <button
              onClick={() => onSummarize(paper.id)}
              disabled={summarizing}
              className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[10px] text-violet-500 hover:text-violet-300 hover:bg-flow-800 disabled:opacity-40 transition-colors"
              title="Re-generate AI summary"
            >
              {summarizing ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Sparkles className="h-3 w-3" />
              )}
              Summarize
            </button>
          </div>
          <div className="flex gap-1">
            {paper.status !== "read" && (
              <button
                onClick={() => onStatusChange(paper.id, "read")}
                className="rounded px-2 py-0.5 font-mono text-[10px] text-flow-500 hover:text-flow-300 hover:bg-flow-800 transition-colors"
              >
                Mark read
              </button>
            )}
            {paper.status !== "archived" && (
              <button
                onClick={() => onStatusChange(paper.id, "archived")}
                className="rounded px-2 py-0.5 font-mono text-[10px] text-flow-600 hover:text-flow-400 hover:bg-flow-800 transition-colors"
              >
                Archive
              </button>
            )}
            <button
              onClick={() => onDeleteFromVault(paper.id)}
              className="rounded px-2 py-0.5 font-mono text-[10px] text-amber-700 hover:text-amber-400 hover:bg-flow-800 transition-colors"
              title="Remove from Obsidian vault"
            >
              <BookX className="inline h-3 w-3" />
            </button>
            <button
              onClick={() => onDelete(paper.id)}
              className="rounded px-2 py-0.5 font-mono text-[10px] text-red-700 hover:text-red-400 hover:bg-flow-800 transition-colors"
              title="Delete paper from DB"
            >
              <Trash2 className="inline h-3 w-3" />
            </button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Digest config modal ───────────────────────────────────────────────

function DigestConfigModal({
  wsId,
  config,
  onSaved,
}: {
  wsId: string;
  config: DigestConfig | null;
  onSaved: (c: DigestConfig) => void;
}) {
  const [open, setOpen] = useState(false);
  const [enabled, setEnabled] = useState(config?.enabled ?? false);
  const [hour, setHour] = useState(String(config?.schedule_hour ?? 8));
  const [minScore, setMinScore] = useState(String(config?.min_relevance_score ?? 0.5));
  const [selectedCats, setSelectedCats] = useState<Set<string>>(
    new Set(config?.arxiv_categories ?? ["cs.AI", "cs.LG", "cs.CL"]),
  );
  const [customCats, setCustomCats] = useState(
    (config?.arxiv_categories ?? []).filter((c) => !ARXIV_CHIPS.some((ch) => ch.code === c)).join(", "),
  );
  const [userInterests, setUserInterests] = useState(config?.user_interests ?? "");
  const [obsidianMode, setObsidianMode] = useState(config?.obsidian_mode ?? "none");
  const [vaultPath, setVaultPath] = useState(config?.obsidian_vault_path ?? "/vault");
  const [customSources, setCustomSources] = useState((config?.custom_sources ?? []).join("\n"));
  const [saving, setSaving] = useState(false);

  function toggleCat(code: string) {
    setSelectedCats((prev) => {
      const next = new Set(prev);
      next.has(code) ? next.delete(code) : next.add(code);
      return next;
    });
  }

  function buildCategories(): string[] {
    const chips = Array.from(selectedCats);
    const extra = customCats.split(",").map((s) => s.trim()).filter(Boolean);
    return [...new Set([...chips, ...extra])];
  }

  async function save() {
    if (!wsId) return;
    setSaving(true);
    try {
      const saved = await apiFetch<DigestConfig>("/api/v1/digest/config", {
        method: "PUT",
        json: {
          workspace_id: wsId,
          enabled,
          schedule_hour: parseInt(hour) || 8,
          min_relevance_score: parseFloat(minScore) || 0.5,
          arxiv_categories: buildCategories(),
          custom_sources: customSources.split("\n").map((s) => s.trim()).filter(Boolean),
          user_interests: userInterests,
          obsidian_mode: obsidianMode,
          obsidian_vault_path: obsidianMode === "filesystem" ? vaultPath : null,
        },
      });
      onSaved(saved);
      setOpen(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5 font-mono text-xs">
          <Settings2 className="h-3.5 w-3.5" />
          Configure
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-mono text-sm">Digest Configuration</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="flex items-center justify-between">
            <Label className="font-mono text-xs">Enable daily digest</Label>
            <Switch checked={enabled} onCheckedChange={setEnabled} />
          </div>
          <div className="space-y-1.5">
            <Label className="font-mono text-xs">Schedule hour (UTC)</Label>
            <Input
              type="number"
              min={0}
              max={23}
              value={hour}
              onChange={(e) => setHour(e.target.value)}
              className="font-mono text-xs"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="font-mono text-xs">Min relevance score (0–1)</Label>
            <Input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={minScore}
              onChange={(e) => setMinScore(e.target.value)}
              className="font-mono text-xs"
            />
          </div>
          <div className="space-y-2">
            <Label className="font-mono text-xs">ArXiv topics</Label>
            <div className="flex flex-wrap gap-1.5">
              {ARXIV_CHIPS.map(({ code, label }) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => toggleCat(code)}
                  className={cn(
                    "rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-semibold transition-colors",
                    selectedCats.has(code)
                      ? "border-violet-500 bg-violet-500/20 text-violet-300"
                      : "border-flow-700 bg-transparent text-flow-500 hover:border-flow-500 hover:text-flow-300",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <Input
              value={customCats}
              onChange={(e) => setCustomCats(e.target.value)}
              placeholder="Extra: cs.DS, cs.NI, …"
              className="font-mono text-xs"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="font-mono text-xs">Research interests</Label>
            <textarea
              value={userInterests}
              onChange={(e) => setUserInterests(e.target.value)}
              rows={3}
              placeholder="I work on LLM reasoning, tool use, and agent architectures…"
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 font-mono text-xs resize-none"
            />
            <p className="text-[10px] text-flow-500 leading-relaxed">
              Plain-text description used by the AI when scoring paper relevance.
            </p>
          </div>
          <div className="space-y-1.5">
            <Label className="font-mono text-xs">Custom source URLs (one per line)</Label>
            <textarea
              value={customSources}
              onChange={(e) => setCustomSources(e.target.value)}
              rows={3}
              placeholder="https://huggingface.co/api/daily_papers"
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 font-mono text-xs resize-none"
            />
            <p className="text-[10px] text-flow-500 leading-relaxed">
              JSON API returning a list or object with a <code className="text-flow-300">papers</code> array.
            </p>
          </div>
          <div className="space-y-1.5">
            <Label className="font-mono text-xs">Obsidian sync</Label>
            <select
              value={obsidianMode}
              onChange={(e) => setObsidianMode(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 font-mono text-xs"
            >
              <option value="none">Disabled</option>
              <option value="filesystem">Filesystem</option>
            </select>
          </div>
          {obsidianMode === "filesystem" && (
            <div className="space-y-1.5">
              <Label className="font-mono text-xs">Vault path (inside container)</Label>
              <Input
                value={vaultPath}
                onChange={(e) => setVaultPath(e.target.value)}
                placeholder="/vault"
                className="font-mono text-xs"
              />
              <p className="text-[10px] text-flow-500 leading-relaxed">
                Set <code className="text-flow-300">FLOW_OBSIDIAN_VAULT_PATH</code> in .env to your vault on disk.
                The container mounts it at /vault.
              </p>
            </div>
          )}
          <Button onClick={save} disabled={saving} className="w-full font-mono text-xs">
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Save"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

const STATUS_TABS = [
  { key: "unread", label: "Unread" },
  { key: "read", label: "Read" },
  { key: "archived", label: "Archived" },
  { key: "", label: "All" },
] as const;

export default function ResearchPage() {
  const wsId = useStore((s) => s.workspaces[0]?.id ?? "");
  const [papers, setPapers] = useState<Paper[]>([]);
  const [config, setConfig] = useState<DigestConfig | null>(null);
  const [status, setStatus] = useState<string>("unread");
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [digestRunning, setDigestRunning] = useState(false);
  const [summarizingIds, setSummarizingIds] = useState<Set<string>>(new Set());
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);
  const [embedding, setEmbedding] = useState(false);
  const [synthesis, setSynthesis] = useState<SynthesisResult | null>(null);
  const [synthesizing, setSynthesizing] = useState(false);
  const [knowledge, setKnowledge] = useState<KnowledgePanel | null>(null);
  const [knowledgeOpen, setKnowledgeOpen] = useState(false);
  const fallbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!wsId) return;
    apiFetch<DigestConfig>(`/api/v1/digest/config?workspace_id=${wsId}`)
      .then(setConfig)
      .catch(() => null);
  }, [wsId]);

  const loadPapers = useCallback(() => {
    if (!wsId) return;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ workspace_id: wsId, limit: "30" });
    if (status) params.set("status", status);
    apiFetch<Paper[]>(`/api/v1/digest/papers?${params}`)
      .then((data) => { setError(null); setPapers(data); })
      .catch((e: unknown) => {
        const msg = e instanceof Error ? e.message : "Failed to load papers";
        setError(msg);
        setPapers([]);
      })
      .finally(() => setLoading(false));
  }, [wsId, status]);

  useEffect(() => { loadPapers(); }, [loadPapers]);

  const handleDigestComplete = useCallback(() => {
    if (fallbackTimerRef.current) {
      clearTimeout(fallbackTimerRef.current);
      fallbackTimerRef.current = null;
    }
    setDigestRunning(false);
    loadPapers();
  }, [loadPapers]);

  async function runDigest() {
    if (!wsId) return;
    setRunning(true);
    try {
      await apiFetch("/api/v1/digest/run", {
        method: "POST",
        json: { workspace_id: wsId },
      });
      setDigestRunning(true);
      // Fallback: if SSE never delivers digest.complete, reload after 300s
      fallbackTimerRef.current = setTimeout(() => {
        setDigestRunning(false);
        loadPapers();
      }, 300_000);
    } finally {
      setRunning(false);
    }
  }

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function exportToObsidian() {
    if (!wsId || selectedIds.size === 0) return;
    setExporting(true);
    try {
      await apiFetch<{ written: number; skipped: number }>("/api/v1/digest/papers/export-obsidian", {
        method: "POST",
        json: { workspace_id: wsId, paper_ids: Array.from(selectedIds) },
      });
      setSelectedIds(new Set());
    } finally {
      setExporting(false);
    }
  }

  async function embedAsKnowledge() {
    if (!wsId || selectedIds.size === 0) return;
    setEmbedding(true);
    try {
      await apiFetch<{ embedded: number }>("/api/v1/digest/papers/embed-knowledge", {
        method: "POST",
        json: { workspace_id: wsId, paper_ids: Array.from(selectedIds) },
      });
      setSelectedIds(new Set());
    } finally {
      setEmbedding(false);
    }
  }

  async function runSynthesis() {
    if (!wsId) return;
    setSynthesizing(true);
    setSynthesis(null);
    try {
      const result = await apiFetch<SynthesisResult>("/api/v1/digest/synthesize", {
        method: "POST",
        json: { workspace_id: wsId, limit: 20 },
      });
      setSynthesis(result);
    } finally {
      setSynthesizing(false);
    }
  }

  async function loadKnowledge() {
    if (!wsId) return;
    const data = await apiFetch<KnowledgePanel>(`/api/v1/digest/knowledge?workspace_id=${wsId}`).catch(() => null);
    if (data) setKnowledge(data);
    setKnowledgeOpen(true);
  }

  async function handleDelete(id: string) {
    await apiFetch(`/api/v1/digest/papers/${id}`, { method: "DELETE" });
    setPapers((prev) => prev.filter((p) => p.id !== id));
    setSelectedIds((prev) => { const next = new Set(prev); next.delete(id); return next; });
  }

  async function handleDeleteFromVault(id: string) {
    await apiFetch(`/api/v1/digest/papers/${id}?delete_from_vault=true`, { method: "DELETE" });
    setPapers((prev) => prev.filter((p) => p.id !== id));
    setSelectedIds((prev) => { const next = new Set(prev); next.delete(id); return next; });
  }

  async function handleDeleteSelected() {
    const ids = Array.from(selectedIds);
    await Promise.all(ids.map((id) => apiFetch(`/api/v1/digest/papers/${id}`, { method: "DELETE" }).catch(() => null)));
    setPapers((prev) => prev.filter((p) => !selectedIds.has(p.id)));
    setSelectedIds(new Set());
  }

  async function handleStatusChange(id: string, newStatus: string) {
    await apiFetch(`/api/v1/digest/papers/${id}`, {
      method: "PATCH",
      json: { status: newStatus },
    });
    setPapers((prev) =>
      prev.map((p) => (p.id === id ? { ...p, status: newStatus as Paper["status"] } : p)),
    );
  }

  async function summarizePaper(id: string) {
    setSummarizingIds((prev) => new Set(prev).add(id));
    try {
      const result = await apiFetch<{ tldr: string | null; key_insights: string | null }>(
        `/api/v1/digest/papers/${id}/summarize`,
        { method: "POST" },
      );
      setPapers((prev) =>
        prev.map((p) =>
          p.id === id ? { ...p, tldr: result.tldr, key_insights: result.key_insights } : p,
        ),
      );
    } finally {
      setSummarizingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-mono text-base font-semibold uppercase tracking-widest text-flow-50">
            Research Digest
          </h1>
          <p className="mt-0.5 text-xs text-flow-500">
            Daily arXiv + HuggingFace papers, filtered and summarised by AI.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={loadKnowledge}
            disabled={!wsId}
            className="gap-1.5 font-mono text-xs"
          >
            <Zap className="h-3.5 w-3.5" />
            Knowledge
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={runSynthesis}
            disabled={synthesizing || !wsId}
            className="gap-1.5 font-mono text-xs"
          >
            {synthesizing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <BrainCircuit className="h-3.5 w-3.5" />
            )}
            Synthesize
          </Button>
          <DigestConfigModal wsId={wsId} config={config} onSaved={setConfig} />
          <Button
            size="sm"
            onClick={runDigest}
            disabled={running || !wsId}
            className="gap-1.5 font-mono text-xs"
          >
            {running ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
            Run now
          </Button>
        </div>
      </div>

      {digestRunning && wsId && (
        <DigestProgress wsId={wsId} onComplete={handleDigestComplete} />
      )}

      {selectedIds.size > 0 && (
        <div className="sticky top-0 z-10 flex items-center gap-3 rounded-lg border border-flow-700 bg-flow-900/95 px-4 py-2 backdrop-blur">
          <span className="font-mono text-xs text-flow-300">{selectedIds.size} selected</span>
          <Button
            size="sm"
            onClick={exportToObsidian}
            disabled={exporting}
            className="gap-1.5 font-mono text-xs"
          >
            {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
            Export to Obsidian
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={embedAsKnowledge}
            disabled={embedding}
            className="gap-1.5 font-mono text-xs"
          >
            {embedding ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BrainCircuit className="h-3.5 w-3.5" />}
            Embed as Knowledge
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={handleDeleteSelected}
            className="gap-1.5 font-mono text-xs"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete Selected
          </Button>
          <button
            onClick={() => setSelectedIds(new Set())}
            className="ml-auto font-mono text-[10px] text-flow-500 hover:text-flow-300 transition-colors"
          >
            Clear
          </button>
        </div>
      )}

      {synthesis && (
        <div className="rounded border border-flow-800 bg-flow-900/50 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BrainCircuit className="h-4 w-4 text-violet-400" />
              <span className="font-mono text-xs uppercase tracking-widest text-flow-400">
                Knowledge Synthesis
              </span>
              <span className="font-mono text-[10px] text-flow-600">
                {synthesis.paper_count} papers
              </span>
            </div>
            <button
              onClick={() => setSynthesis(null)}
              className="font-mono text-[10px] text-flow-600 hover:text-flow-400 transition-colors"
            >
              Dismiss
            </button>
          </div>

          {synthesis.topics.length > 0 && (
            <div className="space-y-1">
              <p className="font-mono text-[10px] uppercase tracking-wide text-flow-600">Topics</p>
              <div className="flex flex-wrap gap-1">
                {synthesis.topics.map((t) => (
                  <Badge key={t} variant="outline" className="h-5 px-2 font-mono text-[10px] border-violet-500/30 text-violet-300">
                    {t}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {synthesis.methods.length > 0 && (
            <div className="space-y-1">
              <p className="font-mono text-[10px] uppercase tracking-wide text-flow-600">Methods & Approaches</p>
              <div className="flex flex-wrap gap-1">
                {synthesis.methods.map((m) => (
                  <Badge key={m} variant="outline" className="h-5 px-2 font-mono text-[10px] border-amber-500/30 text-amber-300">
                    {m}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {synthesis.key_findings && (
            <div className="space-y-1">
              <p className="font-mono text-[10px] uppercase tracking-wide text-flow-600">Key Findings</p>
              <p className="text-xs leading-relaxed text-flow-300 rounded bg-flow-800/40 px-3 py-2">
                {synthesis.key_findings}
              </p>
            </div>
          )}

          {synthesis.open_questions.length > 0 && (
            <div className="space-y-1">
              <p className="font-mono text-[10px] uppercase tracking-wide text-flow-600">Open Questions</p>
              <ul className="space-y-0.5">
                {synthesis.open_questions.map((q) => (
                  <li key={q} className="flex items-start gap-1.5 font-mono text-[11px] text-flow-400">
                    <span className="text-flow-600 shrink-0">—</span>
                    {q}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {knowledgeOpen && knowledge && (
        <div className="rounded border border-flow-800 bg-flow-900/50 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-amber-400" />
              <span className="font-mono text-xs uppercase tracking-widest text-flow-400">
                Qdrant Knowledge
              </span>
              {knowledge.available ? (
                <span className="font-mono text-[10px] text-emerald-400">
                  {knowledge.count} papers embedded
                </span>
              ) : (
                <span className="font-mono text-[10px] text-flow-600">Qdrant unavailable</span>
              )}
            </div>
            <button
              onClick={() => setKnowledgeOpen(false)}
              className="font-mono text-[10px] text-flow-600 hover:text-flow-400 transition-colors"
            >
              Dismiss
            </button>
          </div>
          {knowledge.available && knowledge.papers.length > 0 && (
            <div className="space-y-1.5">
              <p className="font-mono text-[10px] uppercase tracking-wide text-flow-600">
                Embedded papers — agents can search across these via hybrid RAG
              </p>
              <div className="flex flex-wrap gap-1">
                {knowledge.papers.map((p) => (
                  <Badge
                    key={p.id}
                    variant="outline"
                    className="h-5 max-w-[220px] truncate px-2 font-mono text-[10px] border-amber-500/30 text-amber-300"
                    title={p.title}
                  >
                    {p.title}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {knowledge.available && knowledge.papers.length === 0 && (
            <p className="font-mono text-[11px] text-flow-600">
              No papers embedded yet. Select papers and click "Embed as Knowledge".
            </p>
          )}
        </div>
      )}

      {error && (
        <div className="rounded border border-red-800 bg-red-900/20 px-3 py-2 font-mono text-xs text-red-400">
          {error}
        </div>
      )}

      <div className="flex gap-1 border-b border-flow-800 pb-0">
        {STATUS_TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setStatus(key)}
            className={cn(
              "border-b-2 px-3 pb-2 font-mono text-[11px] font-medium uppercase tracking-wider transition-colors",
              status === key
                ? "border-flow-violet text-flow-50"
                : "border-transparent text-flow-500 hover:text-flow-300",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-flow-500" />
        </div>
      ) : papers.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <BookOpen className="h-8 w-8 text-flow-700" />
          <p className="font-mono text-xs text-flow-500">
            No papers yet. Click "Run now" to fetch today's digest.
          </p>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between">
            <span className="font-mono text-[11px] text-flow-500">{papers.length} paper{papers.length !== 1 ? "s" : ""}</span>
            <button
              onClick={() => setSelectedIds(selectedIds.size === papers.length ? new Set() : new Set(papers.map((p) => p.id)))}
              className="font-mono text-[11px] text-flow-400 hover:text-flow-200 transition-colors"
            >
              {selectedIds.size === papers.length ? "Deselect All" : "Select All"}
            </button>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {papers.map((paper) => (
            <PaperCard
              key={paper.id}
              paper={paper}
              onStatusChange={handleStatusChange}
              onSummarize={summarizePaper}
              onDelete={handleDelete}
              onDeleteFromVault={handleDeleteFromVault}
              summarizing={summarizingIds.has(paper.id)}
              selected={selectedIds.has(paper.id)}
              onToggleSelect={toggleSelect}
            />
          ))}
          </div>
        </>
      )}
    </div>
  );
}
