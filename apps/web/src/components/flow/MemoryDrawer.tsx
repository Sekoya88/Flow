"use client";

import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { useStore } from "@/lib/store";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

interface MemoryEntry {
  id: string;
  content: string;
  created_at?: string;
  execution_id?: string | null;
}

interface MemoryDrawerProps {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  workspaceId?: string | null;
  agentId?: string | null;
}

export function MemoryDrawer({ open, onOpenChange, workspaceId, agentId }: MemoryDrawerProps) {
  const tokens = useStore((s) => s.tokens);
  const workingText = tokens.join("");
  const [episodic, setEpisodic] = useState<MemoryEntry[]>([]);
  const [semantic, setSemantic] = useState<MemoryEntry[]>([]);

  useEffect(() => {
    if (!open || !workspaceId || !agentId) return;
    apiFetch<{ episodic: MemoryEntry[]; semantic: MemoryEntry[] }>(
      `/api/v1/memory/tiered?workspace_id=${workspaceId}&agent_id=${agentId}`,
    )
      .then((r) => {
        setEpisodic(r.episodic ?? []);
        setSemantic(r.semantic ?? []);
      })
      .catch(() => {});
  }, [open, workspaceId, agentId]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[min(100vw-2rem,26rem)] gap-0 p-0">
        <SheetHeader className="border-b border-flow-800 px-5 py-4 text-left">
          <SheetTitle className="text-base">Memory</SheetTitle>
        </SheetHeader>

        <Tabs defaultValue="working" className="flex h-full flex-col">
          <TabsList className="mx-5 mt-4 grid w-auto grid-cols-3 rounded-lg">
            <TabsTrigger value="working" className="text-xs">Working</TabsTrigger>
            <TabsTrigger value="episodic" className="text-xs">Episodic</TabsTrigger>
            <TabsTrigger value="semantic" className="text-xs">Semantic</TabsTrigger>
          </TabsList>

          <div className="flex-1 overflow-hidden">
            {/* Working memory — current execution tokens */}
            <TabsContent value="working" className="mt-0 h-full">
              <ScrollArea className="h-full px-5 pb-6 pt-4">
                {workingText ? (
                  <pre className="whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed text-foreground/80">
                    {workingText}
                  </pre>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Working memory holds the current run's output. Start a run to see live content here.
                  </p>
                )}
              </ScrollArea>
            </TabsContent>

            {/* Episodic memory — past run summaries */}
            <TabsContent value="episodic" className="mt-0 h-full">
              <ScrollArea className="h-full px-5 pb-6 pt-4">
                {episodic.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Episodic memories are saved after each run. Complete a run to build history.
                  </p>
                ) : (
                  <ul className="space-y-3">
                    {episodic.map((m) => (
                      <MemoryCard
                        key={m.id}
                        entry={m}
                        tier="episodic"
                        onDelete={async () => {
                          await apiFetch(`/api/v1/memory/episodic/${m.id}?workspace_id=${workspaceId}`, {
                            method: "DELETE",
                          });
                          setEpisodic((prev) => prev.filter((x) => x.id !== m.id));
                        }}
                      />
                    ))}
                  </ul>
                )}
              </ScrollArea>
            </TabsContent>

            {/* Semantic memory — long-term knowledge */}
            <TabsContent value="semantic" className="mt-0 h-full">
              <ScrollArea className="h-full px-5 pb-6 pt-4">
                {semantic.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Semantic memories are promoted from episodic when feedback score is high (&gt; 0.85) or explicitly saved.
                  </p>
                ) : (
                  <ul className="space-y-3">
                    {semantic.map((m) => (
                      <MemoryCard key={m.id} entry={m} tier="semantic" />
                    ))}
                  </ul>
                )}
              </ScrollArea>
            </TabsContent>
          </div>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
}

function MemoryCard({
  entry,
  tier,
  onDelete,
}: {
  entry: MemoryEntry;
  tier: "episodic" | "semantic";
  onDelete?: () => void;
}) {
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    if (!onDelete) return;
    setDeleting(true);
    try {
      await onDelete();
    } finally {
      setDeleting(false);
    }
  }

  return (
    <li
      className={cn(
        "group relative rounded-lg border p-3 text-xs leading-relaxed",
        tier === "semantic"
          ? "border-flow-done/30 bg-flow-done/5"
          : "border-flow-800 bg-muted/20",
      )}
    >
      <p className="pr-6 text-foreground/80">{entry.content}</p>
      {entry.created_at ? (
        <time
          dateTime={entry.created_at}
          className="mt-1.5 block text-[10px] text-muted-foreground/60"
        >
          {new Date(entry.created_at).toLocaleString(undefined, {
            dateStyle: "short",
            timeStyle: "short",
          })}
        </time>
      ) : null}
      {onDelete && (
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="absolute right-2 top-2 rounded p-0.5 text-muted-foreground/40 opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100 disabled:opacity-30"
          aria-label="Delete memory"
        >
          <Trash2 className="h-3 w-3" />
        </button>
      )}
    </li>
  );
}
