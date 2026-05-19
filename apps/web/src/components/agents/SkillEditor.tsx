"use client";

import { useCallback, useState } from "react";
import { FileCode2, Save, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const TEMPLATE = `---
name: my-skill
description: When and how to apply this skill
version: "1.0"
allowed-tools: retrieve, sandbox
triggers:
  - "example trigger phrase"
metadata:
  author: user
---

# My Skill

## Instructions

Describe the skill instructions here. The agent will follow these when a trigger matches.

## Guidelines

- Be specific about the approach
- Reference allowed tools when relevant
`;

interface SkillEditorProps {
  initialContent?: string;
  initialName?: string;
  onSave: (content: string, name: string) => void;
  onCancel: () => void;
  className?: string;
}

export function SkillEditor({
  initialContent,
  initialName,
  onSave,
  onCancel,
  className,
}: SkillEditorProps) {
  const [content, setContent] = useState(initialContent || TEMPLATE);
  const [name, setName] = useState(initialName || "");
  const [saving, setSaving] = useState(false);

  // Parse frontmatter name from content as fallback
  const parsedName = (() => {
    const match = content.match(/^---\s*\n[\s\S]*?name:\s*(.+)/m);
    return match?.[1]?.trim() || "";
  })();

  const effectiveName = name || parsedName || "unnamed";

  const handleSave = useCallback(() => {
    if (!content.trim()) return;
    setSaving(true);
    onSave(content, effectiveName);
    // Parent will close the editor
  }, [content, effectiveName, onSave]);

  // Simple syntax highlighting for YAML frontmatter
  const lineCount = content.split("\n").length;

  return (
    <div className={cn("rounded-[6px] border border-flow-800 bg-card/80 overflow-hidden", className)}>
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-flow-800 px-5 py-3">
        <FileCode2 className="h-4 w-4 text-flow-violet" />
        <span className="text-sm font-medium text-foreground">SKILL.md Editor</span>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onCancel} className="gap-1.5 text-xs h-7">
            <X className="h-3 w-3" />
            Cancel
          </Button>
          <Button size="sm" onClick={handleSave} disabled={saving} className="gap-1.5 text-xs h-7">
            <Save className="h-3 w-3" />
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>

      {/* Name override */}
      <div className="border-b border-border/30 px-5 py-2 flex items-center gap-3">
        <Label className="text-[10px] uppercase tracking-wide text-muted-foreground shrink-0">Name</Label>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={parsedName || "skill-name"}
          className="h-7 text-xs max-w-xs"
        />
        <span className="text-[10px] text-muted-foreground">Overrides frontmatter name</span>
      </div>

      {/* Editor area */}
      <div className="relative">
        {/* Line numbers */}
        <div className="absolute left-0 top-0 bottom-0 w-10 bg-muted/10 border-r border-border/30 pt-4 pb-4 overflow-hidden pointer-events-none">
          <div className="flex flex-col items-end pr-2">
            {Array.from({ length: lineCount }, (_, i) => (
              <span key={i} className="font-mono text-[10px] leading-[1.625rem] text-muted-foreground/40 tabular-nums">
                {i + 1}
              </span>
            ))}
          </div>
        </div>

        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className={cn(
            "w-full min-h-[400px] resize-y",
            "bg-transparent pl-14 pr-5 py-4",
            "font-mono text-xs leading-relaxed text-foreground",
            "placeholder:text-muted-foreground/40",
            "focus:outline-none",
            "border-0",
          )}
          spellCheck={false}
          placeholder="Paste or type your SKILL.md content…"
        />
      </div>

      {/* Footer hint */}
      <div className="border-t border-border/30 px-5 py-2 flex items-center gap-2 text-[10px] text-muted-foreground">
        <span>Format: YAML frontmatter (---) + Markdown body</span>
        <span className="ml-auto tabular-nums">{lineCount} lines</span>
      </div>
    </div>
  );
}
