"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { PreferenceSection } from "@/components/preferences/PreferenceSection";
import { usePreferences } from "@/lib/usePreferences";
import { useWorkspaceId } from "@/lib/useWorkspace";

const FACET_CLASSES = ["style", "tooling", "goal", "veto", "domain", "channel"] as const;

type Tab = "preferences";

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
    </div>
  );
}
