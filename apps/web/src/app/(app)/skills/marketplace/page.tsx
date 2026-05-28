"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  CheckSquare,
  Download,
  FileText,
  Github,
  Loader2,
  Square,
  TriangleAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import { useWorkspaceId } from "@/lib/useWorkspace";

type RepoSkillFile = {
  path: string;
  name: string;
  sha: string;
  size: number;
};

type RepoPreview = {
  repo: string;
  skills: RepoSkillFile[];
  total: number;
  truncated: boolean;
};

type ImportResult = {
  imported: number;
  skills: { id: string; name: string; path: string }[];
  errors: string[];
};

type Phase = "idle" | "previewing" | "ready" | "importing" | "done";

function FileSizeLabel({ bytes }: { bytes: number }) {
  if (bytes < 1024) return <span>{bytes}B</span>;
  return <span>{(bytes / 1024).toFixed(1)}KB</span>;
}

export default function MarketplacePage() {
  const { workspaceId } = useWorkspaceId();

  const [repoUrl, setRepoUrl] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [preview, setPreview] = useState<RepoPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<ImportResult | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

  async function handleBrowse() {
    const url = repoUrl.trim();
    if (!url) return;
    setPhase("previewing");
    setPreviewError(null);
    setPreview(null);
    setSelected(new Set());
    try {
      const data = await apiFetch<RepoPreview>(
        `/api/v1/skills/preview-repo?url=${encodeURIComponent(url)}`,
      );
      setPreview(data);
      // Pre-select all by default
      setSelected(new Set(data.skills.map((s) => s.path)));
      setPhase("ready");
    } catch (e) {
      setPreviewError(String(e));
      setPhase("idle");
    }
  }

  async function handleImport() {
    if (!preview || !workspaceId || selected.size === 0) return;
    setPhase("importing");
    setImportError(null);
    try {
      const data = await apiFetch<ImportResult>("/api/v1/skills/import/repo", {
        method: "POST",
        json: {
          repo_url: repoUrl,
          workspace_id: workspaceId,
          paths: Array.from(selected),
        },
      });
      setResult(data);
      setPhase("done");
    } catch (e) {
      setImportError(String(e));
      setPhase("ready");
    }
  }

  function reset() {
    setRepoUrl("");
    setPhase("idle");
    setPreview(null);
    setPreviewError(null);
    setSelected(new Set());
    setResult(null);
    setImportError(null);
  }

  function toggleAll() {
    if (!preview) return;
    if (selected.size === preview.skills.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(preview.skills.map((s) => s.path)));
    }
  }

  function toggleOne(path: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  const allSelected = preview ? selected.size === preview.skills.length : false;

  return (
    <div className="mx-auto w-full max-w-3xl space-y-8 px-4 pb-12 pt-6 animate-fade-in">
      <Link
        href="/skills"
        className="inline-flex items-center gap-1.5 font-mono text-[11px] text-flow-500 hover:text-flow-200 transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Skills
      </Link>

      {/* Header */}
      <header className="space-y-2">
        <div className="flex items-center gap-2">
          <Github className="h-4 w-4 text-flow-violet" />
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-flow-violet/80">
            Import from GitHub
          </span>
        </div>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          Import Skills from Repo
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground leading-relaxed">
          Paste any public GitHub repository URL. Flow will find all{" "}
          <code className="rounded bg-flow-900 px-1 font-mono text-[11px]">.md</code> skill files — select
          the ones you want, then import them directly to your workspace.
        </p>
      </header>

      {/* URL input */}
      <div className="rounded-xl border border-flow-800 bg-flow-900 p-5 space-y-3">
        <label className="font-mono text-[10px] uppercase tracking-wider text-flow-500">
          GitHub Repository URL
        </label>
        <div className="flex gap-2">
          <Input
            value={repoUrl}
            onChange={(e) => {
              setRepoUrl(e.target.value);
              if (phase === "ready" || phase === "done") reset();
            }}
            onKeyDown={(e) => e.key === "Enter" && void handleBrowse()}
            placeholder="https://github.com/owner/repo  or  owner/repo"
            className="flex-1 font-mono text-xs bg-flow-950 border-flow-700"
            disabled={phase === "previewing" || phase === "importing"}
          />
          <Button
            disabled={!repoUrl.trim() || phase === "previewing" || phase === "importing"}
            onClick={() => void handleBrowse()}
            className="shrink-0 gap-1.5 bg-flow-violet font-mono text-xs text-white hover:bg-flow-violet/90"
          >
            {phase === "previewing" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Github className="h-3.5 w-3.5" />
            )}
            Browse
          </Button>
        </div>

        {previewError && (
          <div className="flex items-start gap-2 rounded-md border border-red-500/20 bg-red-500/5 px-3 py-2 animate-fade-in">
            <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" />
            <p className="font-mono text-[11px] text-red-400">{previewError}</p>
          </div>
        )}
      </div>

      {/* Skill browser */}
      {(phase === "ready" || phase === "importing") && preview && (
        <div className="space-y-3 animate-fade-in">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="font-mono text-sm font-semibold text-flow-100">
                {preview.repo}
              </p>
              <p className="font-mono text-[11px] text-flow-500">
                {preview.total} skill file{preview.total !== 1 ? "s" : ""} found
                {preview.truncated && " (repo truncated by GitHub)"}
              </p>
            </div>
            <button
              onClick={toggleAll}
              disabled={phase === "importing"}
              className="flex items-center gap-1.5 rounded-md border border-flow-700 bg-flow-900 px-2.5 py-1.5 font-mono text-[11px] text-flow-400 hover:bg-flow-800 hover:text-flow-200 transition-colors disabled:opacity-40"
            >
              {allSelected ? (
                <CheckSquare className="h-3.5 w-3.5" />
              ) : (
                <Square className="h-3.5 w-3.5" />
              )}
              {allSelected ? "Deselect all" : "Select all"}
            </button>
          </div>

          <div className="rounded-xl border border-flow-800 bg-flow-950 divide-y divide-flow-800 overflow-hidden">
            {preview.skills.map((skill) => {
              const isSelected = selected.has(skill.path);
              return (
                <button
                  key={skill.path}
                  onClick={() => toggleOne(skill.path)}
                  disabled={phase === "importing"}
                  className={cn(
                    "flex w-full items-center gap-3 px-4 py-3 text-left transition-colors",
                    isSelected
                      ? "bg-flow-violet/5 hover:bg-flow-violet/10"
                      : "hover:bg-flow-900",
                    "disabled:opacity-60 disabled:cursor-not-allowed",
                  )}
                >
                  <div className={cn(
                    "flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors",
                    isSelected
                      ? "border-flow-violet bg-flow-violet"
                      : "border-flow-600 bg-transparent",
                  )}>
                    {isSelected && <span className="h-2 w-2 rounded-sm bg-white" />}
                  </div>
                  <FileText className={cn(
                    "h-3.5 w-3.5 shrink-0",
                    isSelected ? "text-flow-violet" : "text-flow-600",
                  )} />
                  <div className="flex-1 min-w-0">
                    <p className={cn(
                      "truncate font-mono text-xs font-medium",
                      isSelected ? "text-flow-100" : "text-flow-400",
                    )}>
                      {skill.name}
                    </p>
                    <p className="truncate font-mono text-[10px] text-flow-600">{skill.path}</p>
                  </div>
                  <span className="shrink-0 font-mono text-[10px] text-flow-600">
                    <FileSizeLabel bytes={skill.size} />
                  </span>
                </button>
              );
            })}
          </div>

          {importError && (
            <div className="flex items-start gap-2 rounded-md border border-red-500/20 bg-red-500/5 px-3 py-2">
              <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" />
              <p className="font-mono text-[11px] text-red-400">{importError}</p>
            </div>
          )}

          <div className="flex items-center justify-between">
            <p className="font-mono text-[11px] text-flow-500">
              {selected.size} of {preview.total} selected
            </p>
            <Button
              disabled={selected.size === 0 || phase === "importing"}
              onClick={() => void handleImport()}
              className="gap-1.5 bg-flow-violet font-mono text-xs text-white hover:bg-flow-violet/90 disabled:opacity-50"
            >
              {phase === "importing" ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Importing…
                </>
              ) : (
                <>
                  <Download className="h-3.5 w-3.5" />
                  Import {selected.size} skill{selected.size !== 1 ? "s" : ""}
                </>
              )}
            </Button>
          </div>
        </div>
      )}

      {/* Done state */}
      {phase === "done" && result && (
        <div className="space-y-4 animate-fade-in">
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-5 space-y-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-500/15 border border-emerald-500/30">
                <CheckCircle2 className="h-4.5 w-4.5 text-emerald-400" />
              </div>
              <div>
                <p className="font-mono text-sm font-semibold text-emerald-300">
                  {result.imported} skill{result.imported !== 1 ? "s" : ""} imported
                </p>
                <p className="font-mono text-[11px] text-emerald-400/70">
                  Available in your workspace immediately.
                </p>
              </div>
            </div>

            {result.skills.length > 0 && (
              <div className="space-y-1">
                {result.skills.map((s) => (
                  <div key={s.id} className="flex items-center gap-2">
                    <CheckCircle2 className="h-3 w-3 shrink-0 text-emerald-500" />
                    <span className="font-mono text-[11px] text-emerald-300">{s.name}</span>
                    <span className="font-mono text-[10px] text-emerald-500/50">{s.path}</span>
                  </div>
                ))}
              </div>
            )}

            {result.errors.length > 0 && (
              <div className="rounded-md border border-amber-500/20 bg-amber-500/5 p-3 space-y-1">
                <p className="font-mono text-[10px] uppercase tracking-wider text-amber-400/70">
                  {result.errors.length} error{result.errors.length !== 1 ? "s" : ""}
                </p>
                {result.errors.map((err, i) => (
                  <p key={i} className="font-mono text-[11px] text-amber-400">{err}</p>
                ))}
              </div>
            )}
          </div>

          <div className="flex gap-3">
            <Link href="/skills">
              <Button className="bg-flow-violet font-mono text-xs text-white hover:bg-flow-violet/90">
                View in Skills
              </Button>
            </Link>
            <Button
              variant="outline"
              onClick={reset}
              className="border-flow-700 bg-flow-900 font-mono text-xs text-flow-400 hover:bg-flow-800 hover:text-flow-200"
            >
              Import more
            </Button>
          </div>
        </div>
      )}

      {/* Format hint */}
      <div className="rounded-xl border border-flow-800 bg-flow-900/30 p-5 space-y-3">
        <h2 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-flow-500">
          Skill File Format
        </h2>
        <pre className="rounded-lg bg-flow-950 p-3 font-mono text-[10px] leading-relaxed text-flow-400">
{`---
name: my-skill
description: When to trigger this skill
category: Research
allowed-tools: fetch_webpage, tavily_search
triggers:
  - "user asks about X"
---

## Instructions

Your skill instructions here…`}
        </pre>
        <p className="text-[11px] text-muted-foreground/60">
          The <code className="font-mono">name</code>, <code className="font-mono">description</code>,
          and <code className="font-mono">triggers</code> fields drive skill matching. All other fields are optional.
        </p>
      </div>
    </div>
  );
}
