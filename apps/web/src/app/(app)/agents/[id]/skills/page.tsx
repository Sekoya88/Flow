"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Bot,
  ChevronDown,
  ChevronRight,
  Clock,
  FileCode2,
  GitCompare,
  Loader2,
  Plus,
  Sparkles,
  User,
  Zap,
  BrainCircuit,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { SkillEditor } from "@/components/agents/SkillEditor";
import { SkillDiffView } from "@/components/agents/SkillDiffView";
import { EntityGraphButton } from "@/components/graph/EntityGraphButton";
import { ObsidianImportDialog } from "@/components/skills/ObsidianImportDialog";
import { apiFetch } from "@/lib/api";
import { logger } from "@/lib/logger";
import { cn } from "@/lib/utils";

type SkillRow = {
  id: string;
  name: string;
  version: number;
  content_md: string;
  description: string;
  allowed_tools: string[];
  triggers: string[];
  metadata: Record<string, unknown>;
  active: boolean;
  score: number;
  use_count: number;
  created_at: string;
};

type VersionRow = {
  id: string;
  version: number;
  content_md: string;
  active: boolean;
  created_at: string;
};

export default function SkillsPage() {
  const params = useParams<{ id: string }>();
  const agentId = params.id;
  const router = useRouter();

  const [skills, setSkills] = useState<SkillRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [wsId, setWsId] = useState<string | null>(null);
  const [agentName, setAgentName] = useState<string>("");
  const [editing, setEditing] = useState<SkillRow | null>(null);
  const [creating, setCreating] = useState(false);
  const [diffSkill, setDiffSkill] = useState<string | null>(null);
  const [versions, setVersions] = useState<VersionRow[]>([]);
  const [expandedSkill, setExpandedSkill] = useState<string | null>(null);
  const [improving, setImproving] = useState<string | null>(null);
  const [improveMessage, setImproveMessage] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const me = await apiFetch<{ workspaces: { id: string }[] }>("/api/v1/auth/me");
      const w = me.workspaces[0];
      if (!w) return;
      setWsId(w.id);

      const agents = await apiFetch<{ agents: { id: string; name: string }[] }>(
        `/api/v1/workspaces/${w.id}/agents`,
      );
      const agent = agents.agents.find((a) => a.id === agentId);
      if (agent) setAgentName(agent.name);

      const data = await apiFetch<{ skills: SkillRow[] }>(
        `/api/v1/skills?workspace_id=${w.id}&agent_id=${agentId}`,
      );
      setSkills(data.skills ?? []);
    } catch (e) {
      logger.warn("skills load failed", { error: String(e) });
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    load();
  }, [load]);

  const loadVersions = useCallback(async (skillName: string) => {
    try {
      const data = await apiFetch<{ versions: VersionRow[] }>(
        `/api/v1/skills/history?agent_id=${agentId}&name=${encodeURIComponent(skillName)}`,
      );
      setVersions(data.versions ?? []);
    } catch (e) {
      logger.warn("versions load failed", { error: String(e) });
    }
  }, [agentId]);

  const toggleExpand = useCallback((name: string) => {
    if (expandedSkill === name) {
      setExpandedSkill(null);
      setVersions([]);
    } else {
      setExpandedSkill(name);
      void loadVersions(name);
    }
  }, [expandedSkill, loadVersions]);

  const handleSave = useCallback(async (content: string, name: string) => {
    if (!wsId) return;
    try {
      await apiFetch("/api/v1/skills", {
        method: "POST",
        json: {
          workspace_id: wsId,
          agent_id: agentId,
          name,
          content_md: content,
        },
      });
      setEditing(null);
      setCreating(false);
      void load();
    } catch (e) {
      logger.warn("skill save failed", { error: String(e) });
    }
  }, [wsId, agentId, load]);

  const handleDeactivate = useCallback(async (skillId: string) => {
    try {
      await apiFetch(`/api/v1/skills/${skillId}`, { method: "DELETE" });
      void load();
    } catch (e) {
      logger.warn("deactivate failed", { error: String(e) });
    }
  }, [load]);

  const handleImprove = useCallback(async (skillId: string) => {
    setImproving(skillId);
    try {
      const result = await apiFetch<{
        improved: boolean;
        proposal_id?: string;
        candidate_skill_id?: string;
        confidence?: number;
        changelog?: string[];
        failure_analysis?: string;
        reason?: string;
      }>(`/api/v1/skills/${skillId}/improve`, { method: "POST" });

      if (result.improved) {
        const pct = result.confidence !== undefined ? ` (${Math.round(result.confidence * 100)}% confidence)` : "";
        const changes = result.changelog?.length ? ` — ${result.changelog[0]}` : "";
        setImproveMessage((prev) => ({
          ...prev,
          [skillId]: `Improvement proposal created${pct}${changes}. Review it in Proposals.`,
        }));
      } else {
        setImproveMessage((prev) => ({
          ...prev,
          [skillId]: result.reason ?? "No improvement found.",
        }));
      }
      void load();
    } catch (e) {
      let msg = "Failed to generate improvement proposal.";
      if (e instanceof Error && "body" in e) {
        try {
          const parsed = JSON.parse((e as { body: string }).body);
          if (parsed?.detail) msg = parsed.detail;
        } catch {
          /* leave default */
        }
      }
      setImproveMessage((prev) => ({ ...prev, [skillId]: msg }));
      logger.warn("skill improve failed", { error: String(e) });
    } finally {
      setImproving(null);
    }
  }, [load]);

  const handleActivateVersion = useCallback(async (versionId: string, skillName: string) => {
    try {
      await apiFetch(`/api/v1/skills/${versionId}/activate`, { method: "POST" });
      void load();
      void loadVersions(skillName);
    } catch (e) {
      logger.warn("activate version failed", { error: String(e) });
    }
  }, [load, loadVersions]);

  if (editing || creating) {
    return (
      <div className="mx-auto w-full max-w-4xl space-y-4 px-4 pb-10 animate-fade-in">
        <div className="flex items-center gap-2 pt-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => { setEditing(null); setCreating(false); }}
            className="gap-1.5"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back
          </Button>
          <span className="text-sm text-muted-foreground">
            {creating ? "New skill" : `Editing: ${editing?.name}`}
          </span>
        </div>
        <SkillEditor
          initialContent={editing?.content_md ?? ""}
          initialName={editing?.name ?? ""}
          onSave={handleSave}
          onCancel={() => { setEditing(null); setCreating(false); }}
        />
      </div>
    );
  }

  if (diffSkill && versions.length >= 2) {
    return (
      <div className="mx-auto w-full max-w-5xl space-y-4 px-4 pb-10 animate-fade-in">
        <div className="flex items-center gap-2 pt-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => { setDiffSkill(null); setVersions([]); }}
            className="gap-1.5"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back
          </Button>
          <span className="text-sm text-muted-foreground">
            Comparing versions of &ldquo;{diffSkill}&rdquo;
          </span>
        </div>
        <SkillDiffView
          oldContent={versions[1]?.content_md ?? ""}
          newContent={versions[0]?.content_md ?? ""}
          oldLabel={`v${versions[1]?.version}`}
          newLabel={`v${versions[0]?.version}`}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-8 px-4 pb-10 animate-fade-in">
      <FlowPageHeader
        eyebrow={
          <button onClick={() => router.push("/agents")} className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="h-3 w-3" />
            <Badge variant="outline" className="font-mono text-[10px] uppercase tracking-wide">
              {agentName || "Agent"}
            </Badge>
          </button>
        }
        title="Skills"
        description="Reusable instruction modules auto-created by the reflector or manually authored. Each skill is versioned — new saves create a new version."
        actions={
          <div className="flex items-center gap-2">
            {wsId && (
              <EntityGraphButton
                workspaceId={wsId}
                nodeType="agent"
                refId={agentId}
              />
            )}
            {wsId && (
              <ObsidianImportDialog
                agentId={agentId}
                workspaceId={wsId}
                onImported={load}
              />
            )}
            <Button variant="outline" onClick={() => router.push(`/agents/${agentId}/skills/training`)} className="gap-1.5">
              <BrainCircuit className="h-4 w-4" />
              Training
            </Button>
            <Button onClick={() => setCreating(true)} className="gap-1.5">
              <Plus className="h-4 w-4" />
              New skill
            </Button>
          </div>
        }
      />

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      ) : skills.length === 0 ? (
        <div className="flex flex-col items-center gap-5 py-16">
          <div className="flex h-14 w-14 items-center justify-center rounded-[6px] bg-flow-violet/10 border border-flow-violet/20">
            <Sparkles className="h-7 w-7 text-flow-violet/50" />
          </div>
          <div className="text-center space-y-2 max-w-sm">
            <p className="font-semibold text-foreground">No skills yet</p>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Skills are auto-created when the reflector node detects reusable patterns during execution.
              You can also create them manually.
            </p>
          </div>
          <Button onClick={() => setCreating(true)} variant="outline" className="gap-1.5">
            <Plus className="h-3.5 w-3.5" />
            Create manually
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          {skills.map((skill) => {
            const isExpanded = expandedSkill === skill.name;
            const isAuto = skill.metadata?.auto_generated === true || skill.metadata?.author === "flow-reflector";
            return (
              <div
                key={skill.id}
                className="rounded-xl border border-flow-800 bg-card overflow-hidden transition-all"
              >
                {/* Skill header */}
                <button
                  type="button"
                  onClick={() => toggleExpand(skill.name)}
                  className="flex w-full items-center gap-3 px-4 py-3.5 text-left hover:bg-muted/20 transition-colors"
                >
                  {isExpanded ? (
                    <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  )}

                  <FileCode2 className="h-4 w-4 text-flow-violet shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-foreground">{skill.name}</span>
                      <Badge
                        variant="outline"
                        className="h-4 rounded px-1.5 py-0 text-[9px] font-mono tabular-nums"
                      >
                        v{skill.version}
                      </Badge>
                      {isAuto && (
                        <Badge
                          variant="outline"
                          className="h-4 rounded px-1.5 py-0 text-[9px] gap-0.5 border-flow-violet/30 bg-flow-violet/10"
                        >
                          <Sparkles className="h-2 w-2" />
                          auto
                        </Badge>
                      )}
                    </div>
                    {skill.description && (
                      <p className="mt-0.5 text-xs text-muted-foreground truncate max-w-lg">
                        {skill.description}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-3 shrink-0 text-[10px] text-muted-foreground">
                    <span className="flex items-center gap-1 tabular-nums">
                      <Zap className="h-2.5 w-2.5" />
                      {skill.use_count} uses
                    </span>
                    <span className="flex items-center gap-1 tabular-nums">
                      score: {skill.score.toFixed(1)}
                    </span>
                  </div>
                </button>

                {/* Expanded: triggers + actions */}
                {isExpanded && (
                  <div className="border-t border-flow-800 px-4 py-3 space-y-3 animate-slide-up">
                    {skill.triggers.length > 0 && (
                      <div>
                        <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground mb-1">Triggers</p>
                        <div className="flex flex-wrap gap-1">
                          {skill.triggers.map((t, i) => (
                            <span key={i} className="rounded-md bg-muted/30 px-2 py-0.5 text-[10px] text-muted-foreground">
                              {t}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {skill.allowed_tools.length > 0 && (
                      <div>
                        <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground mb-1">Allowed tools</p>
                        <div className="flex flex-wrap gap-1">
                          {skill.allowed_tools.map((t) => (
                            <Badge key={t} variant="outline" className="text-[9px] px-1.5 py-0">
                              {t}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Version history */}
                    {versions.length > 0 && (
                      <div>
                        <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground mb-1.5">Versions</p>
                        <div className="space-y-1">
                          {versions.map((v) => (
                            <div
                              key={v.id}
                              className={cn(
                                "flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs",
                                v.active ? "bg-flow-violet/5 border border-flow-violet/10" : "border border-transparent hover:bg-muted/20",
                              )}
                            >
                              <span className="font-mono tabular-nums font-medium w-8">v{v.version}</span>
                              <Clock className="h-2.5 w-2.5 text-muted-foreground/50" />
                              <span className="text-muted-foreground">
                                {new Date(v.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                              </span>
                              {v.active ? (
                                <Badge variant="outline" className="ml-auto text-[8px] px-1 py-0 h-3.5 border-flow-violet/30 bg-flow-violet/10">
                                  active
                                </Badge>
                              ) : (
                                <button
                                  type="button"
                                  className="ml-auto font-mono text-[8px] uppercase tracking-wide text-muted-foreground hover:text-flow-violet transition-colors px-1.5 py-0.5 rounded border border-transparent hover:border-flow-violet/30"
                                  onClick={() => void handleActivateVersion(v.id, skill.name)}
                                >
                                  Activate
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex gap-2 pt-1 flex-wrap">
                      <Button variant="outline" size="sm" className="gap-1.5 text-xs h-7" onClick={() => setEditing(skill)}>
                        <FileCode2 className="h-3 w-3" />
                        Edit
                      </Button>
                      {versions.length >= 2 && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="gap-1.5 text-xs h-7"
                          onClick={() => {
                            setDiffSkill(skill.name);
                          }}
                        >
                          <GitCompare className="h-3 w-3" />
                          Diff
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        className="gap-1.5 text-xs h-7 text-flow-violet border-flow-violet/30 hover:bg-flow-violet/10"
                        disabled={improving === skill.id}
                        onClick={() => void handleImprove(skill.id)}
                      >
                        {improving === skill.id ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <Sparkles className="h-3 w-3" />
                        )}
                        Improve
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="gap-1.5 text-xs h-7 text-destructive hover:text-destructive ml-auto"
                        onClick={() => void handleDeactivate(skill.id)}
                      >
                        Deactivate
                      </Button>
                    </div>
                    {improveMessage[skill.id] && (
                      <p className="text-[11px] text-flow-violet/80 mt-1">{improveMessage[skill.id]}</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
