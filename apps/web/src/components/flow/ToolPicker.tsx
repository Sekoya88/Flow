"use client";

import { useEffect, useState } from "react";
import { ToolBadge } from "@/components/flow/ToolBadge";
import { apiFetch } from "@/lib/api";

interface ToolMeta {
  name: string;
  description: string;
  parameters_schema: Record<string, unknown>;
  required_capabilities: string[];
}

interface ToolPickerProps {
  enabledTools?: Record<string, boolean>;
  onToggle?: (name: string, enabled: boolean) => void;
  className?: string;
}

export function ToolPicker({ enabledTools = {}, onToggle, className }: ToolPickerProps) {
  const [tools, setTools] = useState<ToolMeta[]>([]);

  useEffect(() => {
    apiFetch<{ tools: ToolMeta[] }>("/api/v1/tools")
      .then((r) => setTools(r.tools))
      .catch(() => {});
  }, []);

  if (tools.length === 0) return null;

  return (
    <div className={className}>
      <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        Plugin tools
      </p>
      <div className="flex flex-wrap gap-2">
        {tools.map((t) => {
          const isCore = ["retrieve", "sandbox", "long_term_memory"].includes(t.name);
          if (isCore) return null;
          const enabled = enabledTools[t.name] ?? false;
          return (
            <button
              key={t.name}
              type="button"
              title={t.description}
              onClick={() => onToggle?.(t.name, !enabled)}
              className="cursor-pointer transition-opacity"
              style={{ opacity: enabled ? 1 : 0.45 }}
            >
              <ToolBadge
                label={t.name.replace(/_/g, " ")}
                status={enabled ? "done" : "idle"}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}
