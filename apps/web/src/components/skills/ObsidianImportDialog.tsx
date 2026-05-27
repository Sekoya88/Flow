"use client";

import { useState } from "react";
import { BookOpen, Download, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

const OBSIDIAN_SKILLS = [
  {
    name: "obsidian-markdown",
    label: "Obsidian Markdown",
    description: "Wikilinks, embeds, callouts, properties",
  },
  {
    name: "obsidian-bases",
    label: "Obsidian Bases",
    description: ".base files — views, filters, formulas",
  },
  {
    name: "json-canvas",
    label: "JSON Canvas",
    description: "Canvas nodes, edges, groups",
  },
  {
    name: "obsidian-cli",
    label: "Obsidian CLI",
    description: "Vault interaction, plugin/theme dev",
  },
  {
    name: "defuddle",
    label: "Defuddle",
    description: "Web page markdown extraction",
  },
];

type Props = {
  agentId: string;
  workspaceId: string;
  onImported?: () => void;
};

export function ObsidianImportDialog({ agentId, workspaceId, onImported }: Props) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set(OBSIDIAN_SKILLS.map((s) => s.name)));
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ imported_count: number; errors: string[] } | null>(null);

  const toggle = (name: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const handleImport = async () => {
    setLoading(true);
    setResult(null);
    try {
      const res = await apiFetch<{ imported_count: number; skills: { id: string; name: string }[]; errors: string[] }>(
        "/api/v1/skills/import/obsidian-skills",
        {
          method: "POST",
          json: {
            agent_id: agentId,
            workspace_id: workspaceId,
            skills: selected.size === OBSIDIAN_SKILLS.length ? null : Array.from(selected),
          },
        }
      );
      setResult({ imported_count: res.imported_count, errors: res.errors ?? [] });
      onImported?.();
    } catch {
      setResult({ imported_count: 0, errors: ["Import failed — check API connection"] });
    } finally {
      setLoading(false);
    }
  };

  const handleOpenChange = (v: boolean) => {
    setOpen(v);
    if (!v) setResult(null);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline" className="gap-1.5">
          <BookOpen className="h-4 w-4" />
          Import Obsidian Skills
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Import Obsidian Skills</DialogTitle>
          <DialogDescription>
            Install skills from{" "}
            <a
              href="https://github.com/kepano/obsidian-skills"
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2 hover:text-foreground"
            >
              kepano/obsidian-skills
            </a>{" "}
            — Obsidian-specific instruction modules for agents.
          </DialogDescription>
        </DialogHeader>

        {result ? (
          <div className="space-y-2 py-2">
            <p className="text-sm font-medium text-green-500">
              Imported {result.imported_count} skill{result.imported_count !== 1 ? "s" : ""}
            </p>
            {result.errors.length > 0 && (
              <ul className="space-y-1">
                {result.errors.map((e, i) => (
                  <li key={i} className="text-xs text-destructive">
                    {e}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <div className="space-y-2 py-2">
            <p className="text-xs text-muted-foreground mb-3">Select skills to import:</p>
            {OBSIDIAN_SKILLS.map((skill) => {
              const active = selected.has(skill.name);
              return (
                <button
                  key={skill.name}
                  onClick={() => toggle(skill.name)}
                  className={cn(
                    "w-full rounded-lg border px-3 py-2.5 text-left text-sm transition-colors",
                    active
                      ? "border-primary bg-primary/5 text-foreground"
                      : "border-border bg-background text-muted-foreground hover:border-border/80 hover:text-foreground"
                  )}
                >
                  <div className="font-medium">{skill.label}</div>
                  <div className="text-xs opacity-70">{skill.description}</div>
                </button>
              );
            })}
          </div>
        )}

        <DialogFooter>
          {result ? (
            <Button onClick={() => handleOpenChange(false)}>Done</Button>
          ) : (
            <>
              <Button variant="outline" onClick={() => handleOpenChange(false)}>
                Cancel
              </Button>
              <Button onClick={handleImport} disabled={loading || selected.size === 0} className="gap-1.5">
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                Import {selected.size > 0 ? `${selected.size} skill${selected.size !== 1 ? "s" : ""}` : ""}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
