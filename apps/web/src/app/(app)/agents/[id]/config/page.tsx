"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PreferenceSection } from "@/components/preferences/PreferenceSection";
import { usePreferences } from "@/lib/usePreferences";
import { useWorkspaceId } from "@/lib/useWorkspace";
import { apiFetch } from "@/lib/api";

const FACET_CLASSES = ["style", "tooling", "goal", "veto", "domain", "channel"] as const;

type Tab = "preferences" | "autonomous" | "knowledge";

interface AgentAutoMode {
  auto_improve_threshold: number | null;
  auto_improve_rollback_delta: number;
}

function AutonomousModeCard({ agentId }: { agentId: string }) {
  const [data, setData] = useState<AgentAutoMode | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [threshold, setThreshold] = useState(0.5);
  const [rollbackDelta, setRollbackDelta] = useState(0.15);
  const [enabled, setEnabled] = useState(false);
  const { workspaceId } = useWorkspaceId();

  useEffect(() => {
    if (!workspaceId) return;
    apiFetch<{ agents: Array<{ id: string; auto_improve_threshold?: number | null; auto_improve_rollback_delta?: number }> }>(
      `/api/v1/workspaces/${workspaceId}/agents`
    )
      .then((res) => {
        const agent = res.agents.find((a) => a.id === agentId);
        if (agent) {
          const t = agent.auto_improve_threshold ?? null;
          const d = agent.auto_improve_rollback_delta ?? 0.15;
          setData({ auto_improve_threshold: t, auto_improve_rollback_delta: d });
          setEnabled(t !== null && t !== undefined);
          setThreshold(t ?? 0.5);
          setRollbackDelta(d);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [agentId, workspaceId]);

  const save = useCallback(async (newEnabled: boolean, newThreshold: number, newDelta: number) => {
    setSaving(true);
    try {
      const res = await apiFetch<AgentAutoMode>(`/api/v1/agents/${agentId}`, {
        method: "PATCH",
        json: {
          auto_improve_threshold: newEnabled ? newThreshold : null,
          auto_improve_rollback_delta: newDelta,
        },
      });
      setData(res);
    } catch {
      // keep current state on error
    } finally {
      setSaving(false);
    }
  }, [agentId]);

  const toggleEnabled = () => {
    const next = !enabled;
    setEnabled(next);
    save(next, threshold, rollbackDelta);
  };

  const commitThreshold = () => save(enabled, threshold, rollbackDelta);
  const commitDelta = () => save(enabled, threshold, rollbackDelta);

  const statusLabel = !enabled
    ? "MANUAL"
    : rollbackDelta > 0
    ? `AUTO + SAFETY (≥${(threshold * 100).toFixed(0)}% confidence)`
    : `AUTO (≥${(threshold * 100).toFixed(0)}% confidence)`;

  const statusColor = !enabled
    ? "text-muted-foreground"
    : "text-flow-violet";

  if (loading) {
    return <p className="text-sm text-muted-foreground py-4">Loading...</p>;
  }

  return (
    <div className="space-y-6">
      {/* Status badge */}
      <div className="flex items-center gap-3">
        <span className={`font-mono text-xs font-semibold tracking-wider uppercase ${statusColor}`}>
          {statusLabel}
        </span>
        {saving && <span className="text-[10px] text-muted-foreground">saving…</span>}
      </div>

      {/* Enable toggle */}
      <div className="flex items-center justify-between rounded-[6px] border border-flow-800 bg-flow-900 p-4">
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">Autonomous Improvement</p>
          <p className="text-xs text-muted-foreground">
            When enabled, passing rewrites are activated without human approval.
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          onClick={toggleEnabled}
          disabled={saving}
          className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
            enabled ? "bg-flow-violet" : "bg-flow-700"
          } disabled:opacity-50`}
        >
          <span
            className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow-lg transition-transform ${
              enabled ? "translate-x-4" : "translate-x-0"
            }`}
          />
        </button>
      </div>

      {/* Confidence threshold */}
      <div className={`space-y-3 rounded-[6px] border border-flow-800 bg-flow-900 p-4 transition-opacity ${!enabled ? "opacity-40 pointer-events-none" : ""}`}>
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-foreground">Confidence Threshold</p>
          <span className="font-mono text-sm text-flow-violet">{(threshold * 100).toFixed(0)}%</span>
        </div>
        <p className="text-xs text-muted-foreground">
          Minimum rewrite confidence required for autonomous promotion. Higher = more conservative.
        </p>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={threshold}
          onChange={(e) => setThreshold(Number(e.target.value))}
          onMouseUp={commitThreshold}
          onTouchEnd={commitThreshold}
          disabled={!enabled || saving}
          className="w-full accent-flow-violet"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground font-mono">
          <span>0% (aggressive)</span>
          <span>100% (never)</span>
        </div>
      </div>

      {/* Safety rollback delta */}
      <div className={`space-y-3 rounded-[6px] border border-flow-800 bg-flow-900 p-4 transition-opacity ${!enabled ? "opacity-40 pointer-events-none" : ""}`}>
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-foreground">Safety Rollback Threshold</p>
          <span className="font-mono text-sm text-flow-violet">−{(rollbackDelta * 100).toFixed(0)}%</span>
        </div>
        <p className="text-xs text-muted-foreground">
          If post-promotion safety eval drops by more than this, the genome is automatically rolled back (runs at 04:30 UTC).
        </p>
        <input
          type="range"
          min={0.01}
          max={0.5}
          step={0.01}
          value={rollbackDelta}
          onChange={(e) => setRollbackDelta(Number(e.target.value))}
          onMouseUp={commitDelta}
          onTouchEnd={commitDelta}
          disabled={!enabled || saving}
          className="w-full accent-flow-violet"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground font-mono">
          <span>1% (tight)</span>
          <span>50% (loose)</span>
        </div>
      </div>

      {/* Info box */}
      <div className="rounded-[6px] border border-flow-800 bg-flow-900/50 p-4 text-xs text-muted-foreground space-y-1">
        <p className="font-medium text-foreground text-xs">How it works</p>
        <ol className="list-decimal list-inside space-y-1 mt-2">
          <li>Golden set evaluation detects failures → curator rewrites prompt</li>
          <li>If rewrite confidence ≥ threshold → genome auto-promoted to ACTIVE</li>
          <li>At 04:30 UTC the next day → safety eval re-runs on promoted genome</li>
          <li>If score dropped &gt; rollback delta → previous genome restored automatically</li>
          <li>All auto-activations logged as audit proposals (visible in Proposals)</li>
        </ol>
      </div>

      {data && (
        <p className="text-[10px] text-muted-foreground font-mono">
          DB state: threshold={data.auto_improve_threshold ?? "NULL"} rollback_delta={data.auto_improve_rollback_delta}
        </p>
      )}
    </div>
  );
}

interface AgentTools {
  retrieve: boolean;
  sandbox: boolean;
  long_term_memory: boolean;
  tavily_search: boolean;
  fetch_webpage: boolean;
  arxiv_search: boolean;
  hf_papers: boolean;
}

const DEFAULT_TOOLS: AgentTools = {
  retrieve: true,
  sandbox: true,
  long_term_memory: true,
  tavily_search: false,
  fetch_webpage: false,
  arxiv_search: false,
  hf_papers: false,
};

function Toggle({ checked, onChange, disabled }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      disabled={disabled}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
        checked ? "bg-flow-violet" : "bg-flow-700"
      } disabled:opacity-50`}
    >
      <span
        className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow-lg transition-transform ${
          checked ? "translate-x-4" : "translate-x-0"
        }`}
      />
    </button>
  );
}

function KnowledgeCard({ agentId }: { agentId: string }) {
  const [tools, setTools] = useState<AgentTools>(DEFAULT_TOOLS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const { workspaceId } = useWorkspaceId();

  useEffect(() => {
    if (!workspaceId) return;
    apiFetch<{ agents: Array<{ id: string; config?: { tools?: Partial<AgentTools> } }> }>(
      `/api/v1/workspaces/${workspaceId}/agents`
    )
      .then((res) => {
        const agent = res.agents.find((a) => a.id === agentId);
        if (agent?.config?.tools) {
          setTools({ ...DEFAULT_TOOLS, ...agent.config.tools });
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [agentId, workspaceId]);

  const patch = useCallback(async (key: keyof AgentTools, value: boolean) => {
    setSaving(key);
    setTools((prev) => ({ ...prev, [key]: value }));
    try {
      await apiFetch(`/api/v1/agents/${agentId}`, {
        method: "PATCH",
        json: { [key]: value },
      });
    } catch {
      setTools((prev) => ({ ...prev, [key]: !value }));
    } finally {
      setSaving(null);
    }
  }, [agentId]);

  if (loading) return <p className="text-sm text-muted-foreground py-4">Loading...</p>;

  const KNOWLEDGE_TOOLS: Array<{ key: keyof AgentTools; label: string; description: string; badge?: string }> = [
    {
      key: "retrieve",
      label: "Semantic Knowledge Base",
      badge: "Qdrant",
      description:
        "Hybrid search over embedded documents (dense OpenAI vectors + sparse BM25). When enabled, the agent retrieves relevant chunks from your workspace's embedded PDFs, notes, and research papers before answering.",
    },
    {
      key: "long_term_memory",
      label: "Episodic Memory",
      badge: "Postgres",
      description:
        "Stores and recalls past conversation snippets. Lets the agent reference prior interactions with the same thread — useful for research or coding agents that benefit from context across sessions.",
    },
  ];

  const OTHER_TOOLS: Array<{ key: keyof AgentTools; label: string; description: string }> = [
    { key: "sandbox", label: "Python Sandbox", description: "Execute Python code in an isolated sandbox during agent runs." },
    { key: "tavily_search", label: "Web Search (Tavily)", description: "Live internet search via Tavily API. Requires FLOW_TAVILY_API_KEY." },
    { key: "fetch_webpage", label: "Fetch Webpage", description: "Fetch and read the full content of any URL." },
    { key: "arxiv_search", label: "arXiv Search", description: "Search academic papers on arXiv.org." },
    { key: "hf_papers", label: "HuggingFace Daily Papers", description: "Fetch today's trending AI/ML papers from HuggingFace." },
  ];

  return (
    <div className="space-y-8">
      {/* Knowledge retrieval section */}
      <div className="space-y-3">
        <div className="space-y-0.5">
          <p className="text-sm font-semibold text-foreground">Knowledge Retrieval</p>
          <p className="text-xs text-muted-foreground">
            Controls how the agent accesses your workspace&apos;s knowledge before generating a response.
          </p>
        </div>
        {KNOWLEDGE_TOOLS.map(({ key, label, badge, description }) => (
          <div
            key={key}
            className="flex items-start gap-4 rounded-[6px] border border-flow-800 bg-flow-900 p-4"
          >
            <div className="flex-1 space-y-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="text-sm font-medium text-foreground">{label}</p>
                {badge && (
                  <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-mono font-medium bg-flow-violet/15 text-flow-violet border border-flow-violet/30">
                    {badge}
                  </span>
                )}
                {saving === key && (
                  <span className="text-[10px] text-muted-foreground">saving…</span>
                )}
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>
            </div>
            <Toggle checked={tools[key]} onChange={(v) => patch(key, v)} disabled={saving !== null} />
          </div>
        ))}
      </div>

      {/* Tools section */}
      <div className="space-y-3">
        <div className="space-y-0.5">
          <p className="text-sm font-semibold text-foreground">Agent Tools</p>
          <p className="text-xs text-muted-foreground">
            Extra capabilities the agent can invoke during a run.
          </p>
        </div>
        {OTHER_TOOLS.map(({ key, label, description }) => (
          <div
            key={key}
            className="flex items-start gap-4 rounded-[6px] border border-flow-800 bg-flow-900 p-4"
          >
            <div className="flex-1 space-y-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium text-foreground">{label}</p>
                {saving === key && (
                  <span className="text-[10px] text-muted-foreground">saving…</span>
                )}
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>
            </div>
            <Toggle checked={tools[key]} onChange={(v) => patch(key, v)} disabled={saving !== null} />
          </div>
        ))}
      </div>

      {/* Info box */}
      <div className="rounded-[6px] border border-flow-800 bg-flow-900/50 p-4 text-xs text-muted-foreground space-y-2">
        <p className="font-medium text-foreground text-xs">How knowledge retrieval works</p>
        <ol className="list-decimal list-inside space-y-1 mt-2">
          <li>User sends a message → agent embeds the query (OpenAI text-embedding-3-small)</li>
          <li>Supervisor LLM routes: RETRIEVE_HYBRID, RETRIEVE_DENSE, or DIRECT_ANSWER</li>
          <li>Hybrid: BM25 sparse + dense cosine, fused via Reciprocal Rank Fusion (RRF)</li>
          <li>Grader LLM filters low-relevance chunks; rewriter refines query if needed</li>
          <li>Retrieved chunks injected into system context before LLM generates answer</li>
        </ol>
        <p className="mt-2">
          Embed documents via the <span className="font-mono text-foreground">Research → Embed as Knowledge</span> action.
          Qdrant dashboard: <span className="font-mono text-foreground">http://localhost:16333/dashboard</span>
        </p>
      </div>
    </div>
  );
}

export default function AgentConfigPage() {
  const params = useParams<{ id: string }>();
  const agentId = params?.id ?? "";
  const { workspaceId, loading: wsLoading } = useWorkspaceId();

  const [activeTab, setActiveTab] = useState<Tab>("preferences");
  const { data, loading, error, patchPreference, createPreference } = usePreferences(workspaceId ?? "", agentId);

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 px-4 pb-10 animate-fade-in">
      <h1 className="text-2xl font-semibold text-foreground">Agent Config</h1>

      {/* Tab navigation */}
      <div className="flex border-b border-flow-800">
        <button
          type="button"
          onClick={() => setActiveTab("preferences")}
          className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
            activeTab === "preferences"
              ? "border-flow-violet text-flow-violet"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Preferences
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("autonomous")}
          className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
            activeTab === "autonomous"
              ? "border-flow-violet text-flow-violet"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Autonomous Mode
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("knowledge")}
          className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
            activeTab === "knowledge"
              ? "border-flow-violet text-flow-violet"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Knowledge & Tools
        </button>
      </div>

      {/* Preferences tab content */}
      {activeTab === "preferences" && (
        <div className="space-y-1">
          {(wsLoading || loading) && (
            <p className="text-sm text-muted-foreground py-4">Loading preferences...</p>
          )}
          {error && (
            <p className="text-sm text-destructive py-4">Failed to load preferences.</p>
          )}
          {!loading && !error && data && (
            <>
              {FACET_CLASSES.map((cls) => (
                <PreferenceSection
                  key={cls}
                  cls={cls}
                  prefs={data.agent_specific.filter((p) => p.class === cls)}
                  globalPrefs={data.global.filter((p) => p.class === cls)}
                  onPatch={patchPreference}
                  onAdd={(c, v) => createPreference(c, v, agentId)}
                />
              ))}
            </>
          )}
        </div>
      )}

      {/* Autonomous Mode tab content */}
      {activeTab === "autonomous" && (
        <AutonomousModeCard agentId={agentId} />
      )}

      {/* Knowledge & Tools tab content */}
      {activeTab === "knowledge" && (
        <KnowledgeCard agentId={agentId} />
      )}
    </div>
  );
}
