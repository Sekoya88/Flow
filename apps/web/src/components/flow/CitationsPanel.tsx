"use client";

import { useState } from "react";
import { ChevronDown, FileText } from "lucide-react";
import { cn } from "@/lib/utils";

export type CitationSource = {
  source_id: string;
  title: string;
  chunk_index: number;
  preview: string;
};

export function CitationsPanel({ citations }: { citations: CitationSource[] }) {
  const [expanded, setExpanded] = useState<number | null>(null);

  if (!citations.length) return null;

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Sources ({citations.length})
      </p>
      <ol className="space-y-1.5 text-sm">
        {citations.map((c, i) => (
          <li key={`${c.source_id}-${c.chunk_index}`}>
            <button
              type="button"
              onClick={() => setExpanded(expanded === i ? null : i)}
              className={cn(
                "w-full flex items-start gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors",
                expanded === i
                  ? "border-primary/40 bg-primary/5"
                  : "border-border/60 bg-muted/5 hover:bg-muted/20",
              )}
            >
              <span className="shrink-0 mt-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-muted text-[10px] font-bold text-muted-foreground">
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
                  <span className="font-medium text-foreground truncate">{c.title}</span>
                  <span className="text-muted-foreground text-xs shrink-0">§{c.chunk_index + 1}</span>
                </div>
                {expanded === i && (
                  <p className="mt-2 whitespace-pre-wrap font-mono text-xs leading-relaxed text-foreground/80 border-t border-border/40 pt-2">
                    {c.preview}
                  </p>
                )}
              </div>
              <ChevronDown
                className={cn(
                  "h-4 w-4 shrink-0 text-muted-foreground transition-transform mt-0.5",
                  expanded === i && "rotate-180",
                )}
                aria-hidden
              />
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
