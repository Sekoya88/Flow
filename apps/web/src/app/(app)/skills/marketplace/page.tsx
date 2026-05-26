"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, Download, ExternalLink, Loader2, Store } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiFetch } from "@/lib/api";
import { useWorkspaceId } from "@/lib/useWorkspace";
import { cn } from "@/lib/utils";

type AgentRow = { id: string; name: string; template: string };
type GistPreview = {
  gist_id: string;
  source_file: string;
  name: string;
  preview: string;
};

export default function MarketplacePage() {
  const { workspaceId } = useWorkspaceId();
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [agentId, setAgentId] = useState<string>("");

  const [gistUrl, setGistUrl] = useState("");
  const [preview, setPreview] = useState<GistPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const [installing, setInstalling] = useState(false);
  const [installed, setInstalled] = useState<string | null>(null);
  const [installError, setInstallError] = useState<string | null>(null);

  useEffect(() => {
    if (!workspaceId) return;
    apiFetch<{ agents: AgentRow[] }>(`/api/v1/workspaces/${workspaceId}/agents`)
      .then((d) => {
        setAgents(d.agents ?? []);
        if (d.agents?.[0]) setAgentId(d.agents[0].id);
      })
      .catch(() => {});
  }, [workspaceId]);

  async function fetchPreview() {
    if (!gistUrl.trim()) return;
    setPreviewing(true);
    setPreview(null);
    setPreviewError(null);
    setInstalled(null);

    // Extract gist ID and call GitHub API directly for preview (no install yet)
    const match = gistUrl.match(/([0-9a-f]{20,})/);
    if (!match) {
      setPreviewError("Could not extract gist ID from URL");
      setPreviewing(false);
      return;
    }
    const gistId = match[1];
    try {
      const resp = await fetch(`https://api.github.com/gists/${gistId}`, {
        headers: { Accept: "application/vnd.github.v3+json" },
      });
      if (!resp.ok) {
        setPreviewError(`GitHub returned ${resp.status}`);
        return;
      }
      const data = await resp.json();
      const files: Record<string, { filename: string; content: string }> = data.files ?? {};
      const mdFiles = Object.values(files).filter((f) => f.filename.endsWith(".md"));
      const file = mdFiles[0] ?? Object.values(files)[0];
      if (!file) {
        setPreviewError("Gist has no files");
        return;
      }

      // Extract name from frontmatter if present
      const nameMatch = file.content.match(/^name:\s*(.+)$/m);
      const name = nameMatch ? nameMatch[1].trim() : file.filename.replace(".md", "");

      setPreview({
        gist_id: gistId,
        source_file: file.filename,
        name,
        preview: file.content.slice(0, 800),
      });
    } catch (e) {
      setPreviewError(String(e));
    } finally {
      setPreviewing(false);
    }
  }

  async function install() {
    if (!preview || !workspaceId || !agentId) return;
    setInstalling(true);
    setInstallError(null);
    setInstalled(null);
    try {
      const result = await apiFetch<{ skill_id: string; name: string }>(
        "/api/v1/skills/import/gist",
        {
          method: "POST",
          json: {
            gist_url: gistUrl,
            agent_id: agentId,
            workspace_id: workspaceId,
          },
        },
      );
      setInstalled(result.name);
      setPreview(null);
      setGistUrl("");
    } catch (e) {
      setInstallError(String(e));
    } finally {
      setInstalling(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-8 px-4 pb-12 pt-6 animate-fade-in">
      <Link
        href="/skills"
        className="inline-flex items-center gap-1.5 font-mono text-[11px] text-flow-500 hover:text-flow-200 transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Skills
      </Link>

      <header className="space-y-2">
        <div className="flex items-center gap-2">
          <Store className="h-4 w-4 text-flow-violet" />
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-flow-violet/80">
            Marketplace
          </span>
        </div>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">Import from Gist</h1>
        <p className="max-w-2xl text-sm text-muted-foreground leading-relaxed">
          Install a skill from any public GitHub Gist. Paste the gist URL below — the first{" "}
          <code className="rounded bg-flow-900 px-1 font-mono text-[11px]">.md</code> file will be
          parsed as a{" "}
          <code className="rounded bg-flow-900 px-1 font-mono text-[11px]">SKILL.md</code>.
        </p>
      </header>

      {/* Import form */}
      <div className="flow-card rounded-[10px] border border-flow-800 p-6 space-y-5">
        <div className="space-y-2">
          <Label className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">
            Gist URL or ID
          </Label>
          <div className="flex gap-2">
            <Input
              value={gistUrl}
              onChange={(e) => {
                setGistUrl(e.target.value);
                setPreview(null);
                setInstalled(null);
                setPreviewError(null);
              }}
              onKeyDown={(e) => e.key === "Enter" && void fetchPreview()}
              placeholder="https://gist.github.com/user/abc123def456..."
              className="flex-1 font-mono text-xs"
            />
            <Button
              variant="outline"
              disabled={previewing || !gistUrl.trim()}
              onClick={() => void fetchPreview()}
              className="shrink-0 gap-1.5 font-mono text-xs"
            >
              {previewing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ExternalLink className="h-3.5 w-3.5" />}
              Preview
            </Button>
          </div>
          {previewError && (
            <p className="font-mono text-[11px] text-destructive animate-fade-in">{previewError}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">
            Install into Agent
          </Label>
          <Select value={agentId} onValueChange={(v) => v && setAgentId(v)}>
            <SelectTrigger className="w-full bg-card font-mono text-xs sm:w-[280px]">
              <SelectValue placeholder="Select agent…" />
            </SelectTrigger>
            <SelectContent>
              {agents.map((a) => (
                <SelectItem key={a.id} value={a.id}>
                  {a.name || a.template}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Preview panel */}
        {preview && (
          <div className="rounded-[8px] border border-flow-violet/30 bg-flow-900/50 p-4 space-y-3 animate-fade-in">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="font-mono text-sm font-semibold text-flow-50">{preview.name}</p>
                <p className="font-mono text-[10px] text-flow-600">
                  {preview.source_file} · gist/{preview.gist_id.slice(0, 8)}…
                </p>
              </div>
              <Badge variant="outline" className="border-flow-violet/30 font-mono text-[9px] text-flow-violet">
                .md
              </Badge>
            </div>
            <pre className="max-h-48 overflow-y-auto rounded-[6px] bg-flow-950 p-3 font-mono text-[10px] leading-relaxed text-flow-300 whitespace-pre-wrap">
              {preview.preview}
              {preview.preview.length >= 800 && "…"}
            </pre>
            <div className="flex items-center justify-between gap-3">
              {installError && (
                <p className="font-mono text-[11px] text-destructive">{installError}</p>
              )}
              <div className="ml-auto flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setPreview(null)}
                  className="font-mono text-xs"
                >
                  Cancel
                </Button>
                <Button
                  disabled={installing || !agentId}
                  onClick={() => void install()}
                  className="gap-1.5 bg-flow-violet text-white hover:bg-flow-violet/80 font-mono text-xs"
                >
                  {installing ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Installing…
                    </>
                  ) : (
                    <>
                      <Download className="h-3.5 w-3.5" />
                      Install Skill
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        )}

        {installed && (
          <div className="flex items-center gap-2 rounded-[6px] border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 animate-fade-in">
            <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
            <div>
              <p className="font-mono text-xs font-semibold text-emerald-400">
                "{installed}" installed
              </p>
              <p className="font-mono text-[10px] text-emerald-400/70">
                Active and ready to use.{" "}
                <Link href="/skills" className="underline hover:text-emerald-300">
                  View in Skills →
                </Link>
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Format hint */}
      <div className="rounded-[8px] border border-flow-800 bg-flow-900/30 p-5 space-y-3">
        <h2 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-flow-500">
          Expected Format
        </h2>
        <pre className={cn(
          "rounded-[6px] bg-flow-950 p-3 font-mono text-[10px] leading-relaxed text-flow-400",
        )}>
{`---
name: my-skill
description: When to trigger this skill
category: Research
allowed-tools: fetch_webpage, tavily_search
triggers:
  - "user asks about X"
---

## Instructions

Your skill body here…`}
        </pre>
        <p className="text-[11px] text-muted-foreground/60">
          The <code className="font-mono">name</code>, <code className="font-mono">description</code>, and <code className="font-mono">triggers</code> fields drive matching. Everything else is optional.
        </p>
      </div>
    </div>
  );
}
