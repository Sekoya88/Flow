"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  Bot,
  Brain,
  Bookmark,
  Clock,
  Code2,
  Database,
  FileCode2,
  Globe,
  GitCompare,
  History,
  Loader2,
  MessageSquare,
  Newspaper,
  Plus,
  RotateCcw,
  Search,
  Sparkles,
  Trash2,
  Workflow,
} from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { ApiError, apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { logger } from "@/lib/logger";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import type { AgentRow } from "./AgentCard";
import { MetacogPanel } from "./MetacogPanel";
import { ConfigDiffView } from "./ConfigDiffView";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

const TOOL_DEFS = [
  { key: "retrieve", label: "Knowledge RAG", icon: Database, description: "Semantic search over uploaded docs" },
  { key: "sandbox", label: "Python Sandbox", icon: Code2, description: "Execute Python code in isolation" },
  { key: "long_term_memory", label: "Long-term Memory", icon: Brain, description: "Remember past conversations" },
  { key: "tavily_search", label: "Web Search", icon: Globe, description: "Search the web via Tavily" },
  { key: "fetch_webpage", label: "Fetch URL", icon: Globe, description: "Read any webpage content" },
  { key: "arxiv_search", label: "ArXiv Search", icon: Search, description: "Search academic papers" },
  { key: "hf_papers", label: "HF Daily Papers", icon: Newspaper, description: "Trending AI/ML research" },
] as const;

const TEMPLATE_COLORS: Record<string, string> = {
  "linear-3": "bg-teal-500",
  deer_flow: "bg-teal-500",
  "tool-agent": "bg-amber-500",
  "researcher-critic-writer": "bg-violet-500",
  "human-in-loop": "bg-rose-500",
  orchestrator: "bg-blue-500",
};

type AgentVersion = {
  id: string;
  version_label: string;
  config_snapshot: Record<string, unknown>;
  template: string;
  created_at: string;
  created_by: string | null;
  prompt_hash: string | null;
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const TOOL_DEFAULTS: Record<string, boolean> = {
  retrieve: true,
  sandbox: true,
  long_term_memory: true,
  tavily_search: false,
  fetch_webpage: false,
  arxiv_search: false,
  hf_papers: false,
};

function getTools(config: Record<string, unknown>): Record<string, boolean> {
  const t = config?.tools;
  if (!t || typeof t !== "object" || Array.isArray(t))
    return { ...TOOL_DEFAULTS };
  return { ...TOOL_DEFAULTS, ...(t as Record<string, boolean>) };
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

interface AgentDetailDrawerProps {
  agent: AgentRow | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onToolToggle?: (agentId: string, tool: string, enabled: boolean) => Promise<void>;
  onDelete?: (agentId: string) => Promise<void>;
  workspaceId?: string | null;
}

type SkillRow = {
  id: string;
  name: string;
  version: number;
  description: string;
  allowed_tools: string[];
  triggers: string[];
  active: boolean;
  score: number;
};

export function AgentDetailDrawer({
  agent,
  open,
  onOpenChange,
  onToolToggle,
  onDelete,
  workspaceId,
}: AgentDetailDrawerProps) {
  const router = useRouter();
  const [localTools, setLocalTools] = useState<Record<string, boolean>>({});
  const [toggleError, setToggleError] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // ── Skills state ──
  const [skills, setSkills] = useState<SkillRow[]>([]);
  const [skillsLoading, setSkillsLoading] = useState(false);
  const [skillsLoaded, setSkillsLoaded] = useState(false);

  useEffect(() => {
    if (agent) setLocalTools(getTools(agent.config));
    // Reset skills when agent changes
    setSkills([]);
    setSkillsLoaded(false);
  }, [agent]);

  const tools = localTools;

  // ── Version state ──
  const [versions, setVersions] = useState<AgentVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [snapshotLabel, setSnapshotLabel] = useState("");
  const [saving, setSaving] = useState(false);
  const [diffChanges, setDiffChanges] = useState<Array<{ key: string; old: unknown; new: unknown }> | null>(null);
  const [diffLabels, setDiffLabels] = useState<[string, string]>(["", ""]);

  const loadVersions = useCallback(async () => {
    if (!agent) return;
    setVersionsLoading(true);
    try {
      const data = await apiFetch<{ versions: AgentVersion[] }>(
        `/api/v1/agents/${agent.id}/versions`,
      );
      setVersions(data.versions ?? []);
    } catch (e) {
      logger.warn("versions load failed", { error: String(e) });
    } finally {
      setVersionsLoading(false);
    }
  }, [agent]);

  const handleSnapshot = useCallback(async () => {
    if (!agent || !snapshotLabel.trim()) return;
    setSaving(true);
    try {
      await apiFetch(`/api/v1/agents/${agent.id}/versions`, {
        method: "POST",
        json: { version_label: snapshotLabel.trim() },
      });
      setSnapshotLabel("");
      void loadVersions();
    } catch (e) {
      logger.warn("snapshot failed", { error: String(e) });
    } finally {
      setSaving(false);
    }
  }, [agent, snapshotLabel, loadVersions]);

  const handleRestore = useCallback(async (versionId: string) => {
    if (!agent) return;
    try {
      await apiFetch(`/api/v1/agents/${agent.id}/versions/${versionId}/restore`, {
        method: "POST",
      });
      void loadVersions();
    } catch (e) {
      logger.warn("restore failed", { error: String(e) });
    }
  }, [agent, loadVersions]);

  const handleDiff = useCallback(async (v1Id: string, v2Id: string) => {
    if (!agent) return;
    try {
      const data = await apiFetch<{ v1: { label: string }; v2: { label: string }; changes: Array<{ key: string; old: unknown; new: unknown }> }>(
        `/api/v1/agents/${agent.id}/versions/${v1Id}/diff/${v2Id}`,
      );
      setDiffChanges(data.changes);
      setDiffLabels([data.v1.label, data.v2.label]);
    } catch (e) {
      logger.warn("diff failed", { error: String(e) });
    }
  }, [agent]);

  const loadSkills = useCallback(async () => {
    if (!agent || !workspaceId || skillsLoaded) return;
    setSkillsLoading(true);
    try {
      const data = await apiFetch<{ skills: SkillRow[] }>(
        `/api/v1/skills?workspace_id=${workspaceId}&agent_id=${agent.id}`,
      );
      setSkills(data.skills ?? []);
      setSkillsLoaded(true);
    } catch (e) {
      logger.warn("skills load failed", { error: String(e) });
    } finally {
      setSkillsLoading(false);
    }
  }, [agent, workspaceId, skillsLoaded]);

  const handleDeactivateSkill = useCallback(async (skillId: string) => {
    try {
      await apiFetch(`/api/v1/skills/${skillId}`, { method: "DELETE" });
      setSkills((prev) => prev.filter((s) => s.id !== skillId));
    } catch (e) {
      logger.warn("skill deactivate failed", { error: String(e) });
    }
  }, []);

  if (!agent) return null;

  const templateColor = TEMPLATE_COLORS[agent.template] ?? "bg-slate-500";

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-md border-l border-flow-800 p-0"
      >
        <ScrollArea className="h-full">
          <div className="flex flex-col">
            {/* Header with gradient */}
            <div className="relative overflow-hidden border-b border-flow-800 px-6 pb-6 pt-6">
              {/* Ambient glow */}
              <div
                className={cn(
                  "pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full blur-3xl opacity-20",
                  templateColor,
                )}
                aria-hidden
              />
              <SheetHeader className="p-0 relative">
                <div className="flex items-center gap-3">
                  <div
                    className={cn(
                      "flex h-10 w-10 items-center justify-center rounded-xl",
                      "border border-flow-800 bg-card/80",
                    )}
                  >
                    <Bot className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <SheetTitle className="truncate text-lg">
                      {agent.name || agent.template}
                    </SheetTitle>
                    <SheetDescription className="flex items-center gap-2">
                      <span
                        className={cn("inline-block h-2 w-2 rounded-full", templateColor)}
                        aria-hidden
                      />
                      {agent.template.replace(/-/g, " ").replace(/_/g, " ")}
                    </SheetDescription>
                  </div>
                </div>
              </SheetHeader>

              {/* Quick stats */}
              <div className="mt-5 grid grid-cols-3 gap-3">
                {[
                  { label: "Runs", value: agent.total_runs ?? 0 },
                  {
                    label: "Confidence",
                    value:
                      agent.avg_confidence !== undefined && agent.avg_confidence > 0
                        ? `${(agent.avg_confidence * 100).toFixed(0)}%`
                        : "—",
                  },
                  {
                    label: "Last run",
                    value: agent.last_run_at
                      ? new Date(agent.last_run_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                        })
                      : "Never",
                  },
                ].map((stat) => (
                  <div
                    key={stat.label}
                    className="rounded-xl border border-flow-800 bg-muted/20 px-3 py-2.5 text-center"
                  >
                    <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      {stat.label}
                    </p>
                    <p className="mt-0.5 font-mono text-lg font-semibold tabular-nums text-foreground">
                      {stat.value}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* Tabs */}
            <Tabs defaultValue="tools" className="flex-1">
              <TabsList className="w-full justify-start border-b border-flow-800 px-6" variant="line">
                <TabsTrigger value="tools">Tools</TabsTrigger>
                <TabsTrigger value="intelligence">Intelligence</TabsTrigger>
                <TabsTrigger value="versions" onClick={() => { if (versions.length === 0) void loadVersions(); }}>Versions</TabsTrigger>
                <TabsTrigger value="config">Config</TabsTrigger>
                <TabsTrigger value="skills" onClick={() => { void loadSkills(); }}>Skills</TabsTrigger>
              </TabsList>

              {/* Tools tab */}
              <TabsContent value="tools" className="px-6 py-4">
                {toggleError && (
                  <Alert variant="destructive" className="mb-3 py-2">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription className="text-xs">{toggleError}</AlertDescription>
                  </Alert>
                )}
                <div className="space-y-1">
                  {TOOL_DEFS.map(({ key, label, icon: Icon, description }) => {
                    const enabled = !!tools[key];
                    return (
                      <div
                        key={key}
                        className={cn(
                          "flex items-center gap-3 rounded-xl px-3 py-3 transition-colors",
                          enabled
                            ? "bg-flow-violet/5 border border-flow-violet/10"
                            : "border border-transparent hover:bg-muted/30",
                        )}
                      >
                        <Icon
                          className={cn(
                            "h-4 w-4 shrink-0",
                            enabled ? "text-flow-violet" : "text-muted-foreground/50",
                          )}
                        />
                        <div className="min-w-0 flex-1">
                          <p
                            className={cn(
                              "text-sm font-medium",
                              enabled ? "text-foreground" : "text-muted-foreground",
                            )}
                          >
                            {label}
                          </p>
                          <p className="text-[11px] text-muted-foreground/70">{description}</p>
                        </div>
                        <Switch
                          size="sm"
                          checked={enabled}
                          onCheckedChange={(checked: boolean) => {
                            const prev = localTools;
                            setLocalTools((p) => ({ ...p, [key]: checked }));
                            setToggleError(null);
                            void onToolToggle?.(agent.id, key, checked)?.catch(() => {
                              setLocalTools(prev);
                              setToggleError(`Failed to ${checked ? "enable" : "disable"} ${label}. Try again.`);
                            });
                          }}
                        />
                      </div>
                    );
                  })}
                </div>
              </TabsContent>

              {/* Intelligence tab */}
              <TabsContent value="intelligence" className="px-6 py-4">
                <MetacogPanel agentId={agent.id} />
              </TabsContent>

              {/* Versions tab */}
              <TabsContent value="versions" className="px-6 py-4">
                <div className="space-y-4">
                  {/* Snapshot form */}
                  <div className="flex gap-2">
                    <Input
                      value={snapshotLabel}
                      onChange={(e) => setSnapshotLabel(e.target.value)}
                      placeholder="Version label (e.g. v2-with-arxiv)"
                      className="h-8 text-xs flex-1"
                      onKeyDown={(e) => { if (e.key === "Enter") void handleSnapshot(); }}
                    />
                    <Button
                      size="sm"
                      className="h-8 gap-1 text-xs"
                      disabled={saving || !snapshotLabel.trim()}
                      onClick={() => void handleSnapshot()}
                    >
                      <Bookmark className="h-3 w-3" />
                      {saving ? "Saving…" : "Snapshot"}
                    </Button>
                  </div>

                  {/* Diff panel */}
                  {diffChanges && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-foreground">Config diff</span>
                        <Button variant="ghost" size="sm" className="h-6 text-[10px]" onClick={() => setDiffChanges(null)}>
                          Close
                        </Button>
                      </div>
                      <ConfigDiffView
                        changes={diffChanges}
                        oldLabel={diffLabels[0]}
                        newLabel={diffLabels[1]}
                      />
                    </div>
                  )}

                  {/* Version list */}
                  {versionsLoading ? (
                    <div className="flex justify-center py-4">
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                    </div>
                  ) : versions.length === 0 ? (
                    <div className="flex flex-col items-center gap-2 py-6 text-center">
                      <History className="h-6 w-6 text-muted-foreground/30" />
                      <p className="text-xs text-muted-foreground">
                        No versions yet. Snapshot your current config to start tracking changes.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      {versions.map((v, i) => (
                        <div
                          key={v.id}
                          className="rounded-lg border border-flow-800 px-3 py-2.5 space-y-1.5"
                        >
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-medium text-foreground">{v.version_label}</span>
                            {v.prompt_hash ? (
                              <span
                                title={`prompt SHA-256: ${v.prompt_hash}`}
                                className="rounded border border-flow-violet/30 bg-flow-violet/10 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-flow-violet/90"
                              >
                                cache:{v.prompt_hash.slice(0, 8)}
                              </span>
                            ) : (
                              <span
                                title="No prompt hash recorded yet — run the agent once to populate"
                                className="rounded border border-flow-800 bg-muted/30 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60"
                              >
                                cache:—
                              </span>
                            )}
                            <span className="text-[10px] text-muted-foreground ml-auto">
                              <Clock className="inline h-2.5 w-2.5 mr-0.5" />
                              {new Date(v.created_at).toLocaleDateString(undefined, {
                                month: "short",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </span>
                          </div>
                          <div className="flex gap-1.5">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 px-2 text-[10px] gap-1"
                              onClick={() => void handleRestore(v.id)}
                            >
                              <RotateCcw className="h-2.5 w-2.5" />
                              Restore
                            </Button>
                            {i < versions.length - 1 && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 px-2 text-[10px] gap-1"
                                onClick={() => void handleDiff(versions[i + 1].id, v.id)}
                              >
                                <GitCompare className="h-2.5 w-2.5" />
                                Diff prev
                              </Button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </TabsContent>

              {/* Config tab */}
              <TabsContent value="config" className="px-6 py-4">
                <div className="space-y-4">
                  <div>
                    <Label className="text-xs text-muted-foreground uppercase tracking-wide">
                      Agent ID
                    </Label>
                    <p className="mt-1 font-mono text-xs text-foreground/80 select-all">
                      {agent.id}
                    </p>
                  </div>
                  <Separator />
                  <div>
                    <Label className="text-xs text-muted-foreground uppercase tracking-wide">
                      Template
                    </Label>
                    <p className="mt-1 font-mono text-sm text-foreground">{agent.template}</p>
                  </div>
                  <Separator />
                  <div>
                    <Label className="text-xs text-muted-foreground uppercase tracking-wide">
                      Raw config
                    </Label>
                    <pre className="mt-2 max-h-64 overflow-auto rounded-lg border border-flow-800 bg-muted/20 p-3 font-mono text-[11px] text-muted-foreground">
                      {JSON.stringify(agent.config, null, 2)}
                    </pre>
                  </div>
                </div>
              </TabsContent>

              {/* Skills tab */}
              <TabsContent value="skills" className="px-6 py-4">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-xs text-muted-foreground">Active skills for this agent</p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-6 gap-1 text-[10px] px-2"
                      onClick={() => { onOpenChange(false); router.push(`/agents/${agent.id}/skills`); }}
                    >
                      <FileCode2 className="h-3 w-3" />
                      Manage
                    </Button>
                    <Button
                      size="sm"
                      className="h-6 gap-1 text-[10px] px-2"
                      onClick={() => { onOpenChange(false); router.push(`/agents/${agent.id}/skills`); }}
                    >
                      <Plus className="h-3 w-3" />
                      New skill
                    </Button>
                  </div>
                </div>

                {skillsLoading ? (
                  <div className="space-y-2">
                    {[1, 2].map((i) => (
                      <div key={i} className="rounded-xl border border-flow-800 p-3 space-y-1.5 animate-pulse">
                        <div className="h-2.5 w-1/2 rounded bg-muted/60" />
                        <div className="h-2 w-3/4 rounded bg-muted/40" />
                      </div>
                    ))}
                  </div>
                ) : skills.length === 0 ? (
                  <div className="flex flex-col items-center gap-3 py-6 text-center">
                    <Sparkles className="h-7 w-7 text-muted-foreground/30" />
                    <p className="text-sm text-muted-foreground">No skills yet.</p>
                    <p className="text-xs text-muted-foreground/70">
                      Skills are auto-created by the reflector node or can be added manually.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {skills.map((skill) => (
                      <div
                        key={skill.id}
                        className="rounded-xl border border-flow-800 bg-card/50 p-3 space-y-1.5"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5">
                              <p className="text-xs font-semibold truncate">{skill.name}</p>
                              <Badge variant="outline" className="text-[9px] px-1 py-0 h-4">
                                v{skill.version}
                              </Badge>
                              <span className="text-[10px] text-muted-foreground tabular-nums">
                                {skill.score.toFixed(1)}★
                              </span>
                            </div>
                            {skill.description && (
                              <p className="text-[11px] text-muted-foreground line-clamp-2 mt-0.5">
                                {skill.description}
                              </p>
                            )}
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 px-1.5 text-[10px] text-muted-foreground hover:text-destructive shrink-0"
                            onClick={() => void handleDeactivateSkill(skill.id)}
                            title="Deactivate skill"
                          >
                            ×
                          </Button>
                        </div>
                        {skill.allowed_tools.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {skill.allowed_tools.map((t) => (
                              <span key={t} className="rounded px-1 py-0.5 text-[9px] bg-muted/50 text-muted-foreground border border-border/30">
                                {t.replace(/_/g, " ")}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </TabsContent>
            </Tabs>

            {/* Footer actions */}
            <div className="border-t border-flow-800 p-4 flex gap-2">
              <Button
                className="flex-1 gap-1.5"
                onClick={() => {
                  onOpenChange(false);
                  router.push(`/run`);
                }}
              >
                <MessageSquare className="h-3.5 w-3.5" />
                Run this agent
              </Button>
              {onDelete && agent && (
                <Button
                  variant="outline"
                  size="icon"
                  disabled={deleteLoading}
                  className="text-destructive border-destructive/30 hover:bg-destructive/10 hover:border-destructive/60 transition-colors"
                  aria-label="Delete agent"
                  onClick={async () => {
                    if (!confirm(`Delete agent "${agent.name}"? This cannot be undone.`)) return;
                    setDeleteLoading(true);
                    try {
                      await onDelete(agent.id);
                      onOpenChange(false);
                    } finally {
                      setDeleteLoading(false);
                    }
                  }}
                >
                  {deleteLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                </Button>
              )}
            </div>
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
