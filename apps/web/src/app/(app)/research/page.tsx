"use client";

import { useEffect, useState } from "react";
import {
  BookOpen,
  ExternalLink,
  Loader2,
  Play,
  RefreshCw,
  Settings2,
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
};

function PaperCard({
  paper,
  onStatusChange,
}: {
  paper: Paper;
  onStatusChange: (id: string, status: string) => void;
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
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

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
  const [categories, setCategories] = useState(
    (config?.arxiv_categories ?? ["cs.AI", "cs.LG", "cs.CL"]).join(", "),
  );
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const saved = await apiFetch<DigestConfig>("/api/v1/digest/config", {
        method: "PUT",
        body: JSON.stringify({
          workspace_id: wsId,
          enabled,
          schedule_hour: parseInt(hour) || 8,
          min_relevance_score: parseFloat(minScore) || 0.5,
          arxiv_categories: categories
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        }),
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
      <DialogContent className="max-w-md">
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
          <div className="space-y-1.5">
            <Label className="font-mono text-xs">ArXiv categories (comma-separated)</Label>
            <Input
              value={categories}
              onChange={(e) => setCategories(e.target.value)}
              placeholder="cs.AI, cs.LG, cs.CL"
              className="font-mono text-xs"
            />
          </div>
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

  useEffect(() => {
    if (!wsId) return;
    apiFetch<DigestConfig>(`/api/v1/digest/config?workspace_id=${wsId}`)
      .then(setConfig)
      .catch(() => null);
  }, [wsId]);

  useEffect(() => {
    if (!wsId) return;
    setLoading(true);
    const params = new URLSearchParams({ workspace_id: wsId, limit: "30" });
    if (status) params.set("status", status);
    apiFetch<Paper[]>(`/api/v1/digest/papers?${params}`)
      .then(setPapers)
      .catch(() => setPapers([]))
      .finally(() => setLoading(false));
  }, [wsId, status]);

  async function runDigest() {
    if (!wsId) return;
    setRunning(true);
    try {
      await apiFetch("/api/v1/digest/run", {
        method: "POST",
        body: JSON.stringify({ workspace_id: wsId }),
      });
    } finally {
      setRunning(false);
    }
  }

  async function handleStatusChange(id: string, newStatus: string) {
    await apiFetch(`/api/v1/digest/papers/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: newStatus }),
    });
    setPapers((prev) =>
      prev.map((p) => (p.id === id ? { ...p, status: newStatus as Paper["status"] } : p)),
    );
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
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {papers.map((paper) => (
            <PaperCard key={paper.id} paper={paper} onStatusChange={handleStatusChange} />
          ))}
        </div>
      )}
    </div>
  );
}
