"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, BookOpen, BookOpenCheck, BrainCircuit, FileUp, Loader2, Sparkles, Trash2 } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { ApiError, apiFetch } from "@/lib/api";
import { track } from "@/lib/analytics";
import { getToken } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Me = { workspaces: { id: string }[] };

type AgentRow = { id: string; name: string; template: string };

type SourceRow = {
  id: string;
  title: string;
  created_at: string;
  chunk_count?: number;
  ingest_status?: string;
  ingest_error?: string;
};

type Sources = { sources: SourceRow[]; has_more?: boolean };

const SOURCES_PAGE_SIZE = 100;

type Chunk = { id: string; index: number; content: string };

function statusVariant(s: string | undefined): "default" | "secondary" | "destructive" | "outline" {
  if (s === "indexed") return "secondary";
  if (s === "processing") return "outline";
  if (s === "failed") return "destructive";
  return "outline";
}

function SourceDetailDrawer({
  source,
  wsId,
  agents,
  onClose,
}: {
  source: SourceRow | null;
  wsId: string;
  agents: AgentRow[];
  onClose: () => void;
}) {
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [pickAgentForChunk, setPickAgentForChunk] = useState<string | null>(null);
  const [promotingChunk, setPromotingChunk] = useState<string | null>(null);

  useEffect(() => {
    if (!source) return;
    setChunks([]);
    setErr(null);
    setLoading(true);
    apiFetch<{ chunks: Chunk[] }>(
      `/api/v1/knowledge/${source.id}/chunks?workspace_id=${wsId}`
    )
      .then((r) => setChunks(r.chunks))
      .catch((e) => setErr(e instanceof ApiError ? `${e.status}: ${e.body}` : String(e)))
      .finally(() => setLoading(false));
  }, [source, wsId]);

  async function promote(chunkId: string, agentId: string) {
    setPromotingChunk(chunkId);
    try {
      await apiFetch(`/api/v1/knowledge/chunks/${chunkId}/promote`, {
        method: "POST",
        json: { workspace_id: wsId, agent_id: agentId },
      });
      toast.success("Added to agent memory");
      setPickAgentForChunk(null);
    } catch (e) {
      toast.error(e instanceof ApiError ? `Promote failed (${e.status})` : "Promote failed");
    } finally {
      setPromotingChunk(null);
    }
  }

  return (
    <Sheet open={source !== null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="flex h-dvh w-[min(100vw-1rem,32rem)] flex-col gap-0 overflow-hidden sm:max-w-lg">
        <SheetHeader className="border-b border-flow-800 pb-4 text-left">
          <SheetTitle className="pr-8 line-clamp-2">{source?.title ?? "Source"}</SheetTitle>
          <SheetDescription>
            {source ? (
              <>
                {new Date(source.created_at).toLocaleString()}
                {" · "}
                {source.chunk_count ?? 0} chunks
                {source.ingest_status ? (
                  <>
                    {" · "}
                    <Badge variant={statusVariant(source.ingest_status)} className="text-[10px] capitalize">
                      {source.ingest_status}
                    </Badge>
                  </>
                ) : null}
              </>
            ) : null}
          </SheetDescription>
        </SheetHeader>

        <ScrollArea className="flex-1 px-1">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-10 text-muted-foreground text-sm">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              Loading chunks…
            </div>
          ) : err ? (
            <p className="p-4 text-sm text-destructive">{err}</p>
          ) : chunks.length === 0 ? (
            <div className="p-4 text-center">
              <BookOpen className="mx-auto mb-2 h-6 w-6 text-muted-foreground/40" aria-hidden />
              <p className="text-sm text-muted-foreground">No chunks indexed yet.</p>
            </div>
          ) : (
            <div className="space-y-3 p-4">
              {chunks.map((c) => (
                <div
                  key={c.id}
                  className="rounded-lg border border-flow-800 bg-muted/10 px-3 py-2.5"
                >
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60">
                      Chunk {c.index + 1}
                    </p>
                    {agents.length > 0 ? (
                      pickAgentForChunk === c.id ? (
                        <Select
                          onValueChange={(agentId) => agentId && void promote(c.id, agentId as string)}
                          disabled={promotingChunk === c.id}
                        >
                          <SelectTrigger className="h-6 w-[140px] text-[10px]">
                            <SelectValue placeholder="Pick agent…" />
                          </SelectTrigger>
                          <SelectContent>
                            {agents.map((a) => (
                              <SelectItem key={a.id} value={a.id} className="text-xs">
                                {a.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setPickAgentForChunk(c.id)}
                          disabled={promotingChunk === c.id}
                          className="flex shrink-0 items-center gap-1 rounded-md border border-flow-violet/30 bg-flow-violet/10 px-2 py-0.5 text-[10px] font-medium text-flow-violet transition-colors hover:bg-flow-violet/20 disabled:opacity-50"
                        >
                          {promotingChunk === c.id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <BrainCircuit className="h-3 w-3" />
                          )}
                          Use in agent memory
                        </button>
                      )
                    ) : null}
                  </div>
                  <p className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-foreground/80">
                    {c.content}
                  </p>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}

export default function KnowledgePage() {
  const router = useRouter();
  const routerRef = useRef(router);
  const fileRef = useRef<HTMLInputElement>(null);
  const [wsId, setWsId] = useState<string | null>(null);
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [title, setTitle] = useState("Notes");
  const [body, setBody] = useState("");
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [selectedSource, setSelectedSource] = useState<SourceRow | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [loadingWs, setLoadingWs] = useState(true);
  const [loadingSources, setLoadingSources] = useState(false);
  const [listErr, setListErr] = useState<string | null>(null);
  const [ingesting, setIngesting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const [urlInput, setUrlInput] = useState("");
  const [crawling, setCrawling] = useState(false);
  const [crawlMsg, setCrawlMsg] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [hasMoreSources, setHasMoreSources] = useState(false);
  const [loadingMoreSources, setLoadingMoreSources] = useState(false);

  const loadSources = useCallback(async (id: string) => {
    setLoadingSources(true);
    setListErr(null);
    try {
      const r = await apiFetch<Sources>(`/api/v1/knowledge?workspace_id=${id}&limit=${SOURCES_PAGE_SIZE}&offset=0`);
      setSources(r.sources);
      setHasMoreSources(r.has_more ?? false);
      track("knowledge_list_viewed", { count: r.sources.length });
    } catch (e) {
      setListErr(e instanceof ApiError ? `${e.status}: ${e.body}` : String(e));
    } finally {
      setLoadingSources(false);
    }
  }, []);

  const loadMoreSources = useCallback(async () => {
    if (!wsId) return;
    setLoadingMoreSources(true);
    try {
      const r = await apiFetch<Sources>(
        `/api/v1/knowledge?workspace_id=${wsId}&limit=${SOURCES_PAGE_SIZE}&offset=${sources.length}`,
      );
      setSources((prev) => [...prev, ...r.sources]);
      setHasMoreSources(r.has_more ?? false);
    } catch {
      toast.error("Failed to load more sources");
    } finally {
      setLoadingMoreSources(false);
    }
  }, [wsId, sources.length]);

  useEffect(() => {
    routerRef.current = router;
  }, [router]);

  useEffect(() => {
    if (!getToken()) {
      routerRef.current.replace("/login");
      return;
    }
    setLoadingWs(true);
    apiFetch<Me>("/api/v1/auth/me")
      .then((m) => {
        const w = m.workspaces[0];
        if (!w) {
          setListErr("No workspace for this account.");
          return;
        }
        setWsId(w.id);
        void loadSources(w.id);
        apiFetch<{ agents: AgentRow[] }>(`/api/v1/workspaces/${w.id}/agents`)
          .then((r) => setAgents(r.agents))
          .catch(() => undefined);
      })
      .catch((e) => {
        setListErr(e instanceof ApiError ? `${e.status}: ${e.body}` : "Could not load workspace.");
      })
      .finally(() => setLoadingWs(false));
  }, [loadSources]);

  async function ingest() {
    if (!wsId) return;
    setMsg(null);
    setIngesting(true);
    try {
      await apiFetch("/api/v1/knowledge", {
        method: "POST",
        json: { workspace_id: wsId, title, body },
      });
      setBody("");
      await loadSources(wsId);
      setMsg("Ingested.");
      track("knowledge_ingest_text", { workspace_id: wsId });
    } catch (e) {
      setMsg(e instanceof ApiError ? `${e.status}: ${e.body}` : String(e));
    } finally {
      setIngesting(false);
    }
  }

  async function onPickFile(f: File | null) {
    if (!f || !wsId) return;
    setUploadMsg(null);
    setUploading(true);
    try {
      const fd = new FormData();
      fd.set("workspace_id", wsId);
      fd.set("file", f);
      await apiFetch("/api/v1/knowledge/upload", { method: "POST", body: fd });
      await loadSources(wsId);
      setUploadMsg(`Uploaded "${f.name}".`);
      track("knowledge_upload", { workspace_id: wsId, filename: f.name });
    } catch (e) {
      setUploadMsg(e instanceof ApiError ? `${e.status}: ${e.body}` : String(e));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function deleteSource(sourceId: string, title: string) {
    if (!wsId) return;
    if (!confirm(`Delete source "${title}"? This cannot be undone.`)) return;
    setDeletingId(sourceId);
    try {
      await apiFetch(`/api/v1/knowledge/${sourceId}`, { method: "DELETE" });
      setSources((prev) => prev.filter((s) => s.id !== sourceId));
      if (selectedSource?.id === sourceId) setSelectedSource(null);
      toast.success(`Source "${title}" deleted`);
    } catch (e) {
      toast.error(e instanceof ApiError ? `Delete failed (${e.status})` : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  }

  async function crawl() {
    if (!wsId || !urlInput.trim()) return;
    setCrawlMsg(null);
    setCrawling(true);
    try {
      await apiFetch("/api/v1/knowledge/crawl", {
        method: "POST",
        json: { workspace_id: wsId, url: urlInput.trim() },
      });
      setUrlInput("");
      await loadSources(wsId);
      setCrawlMsg("URL indexed.");
      track("knowledge_crawl", { workspace_id: wsId });
    } catch (e) {
      setCrawlMsg(e instanceof ApiError ? `${e.status}: ${e.body}` : String(e));
    } finally {
      setCrawling(false);
    }
  }

  if (loadingWs) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground text-sm">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Loading workspace…
      </div>
    );
  }

  if (!wsId && listErr) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Workspace</AlertTitle>
        <AlertDescription>{listErr}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-10 pb-8 animate-fade-in">
      {wsId && (
        <SourceDetailDrawer
          source={selectedSource}
          wsId={wsId}
          agents={agents}
          onClose={() => setSelectedSource(null)}
        />
      )}

      <header className="space-y-2 animate-fade-in">
        <div className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-flow-violet" />
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-flow-violet/80">
            Knowledge
          </span>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-1.5">
            <h1 className="text-3xl font-semibold tracking-tight text-foreground">
              Sources & retrieval corpus
            </h1>
            <p className="max-w-2xl text-sm text-muted-foreground leading-relaxed">
              Sources are chunked and embedded for retrieval during runs. Upload small text files or paste content manually.
            </p>
          </div>
          <Link
            href="/run"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }), "inline-flex w-fit items-center gap-1.5")}
          >
            <Sparkles className="h-3.5 w-3.5" aria-hidden />
            Back to Run
          </Link>
        </div>
      </header>

      {listErr ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Could not load sources</AlertTitle>
          <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <span>{listErr}</span>
            {wsId ? (
              <Button type="button" size="sm" variant="outline" onClick={() => void loadSources(wsId)}>
                Retry
              </Button>
            ) : null}
          </AlertDescription>
        </Alert>
      ) : null}

      <Card className="gap-6 py-6">
        <CardHeader className="px-6">
          <CardTitle className="text-lg">Upload file</CardTitle>
          <CardDescription className="text-[13px] leading-relaxed">
            <code className="text-foreground/80">.txt</code>, <code className="text-foreground/80">.md</code>,{" "}
            <code className="text-foreground/80">.pdf</code>, <code className="text-foreground/80">.docx</code> — max
            20MB. Requires OpenAI key on the API for embeddings.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 px-6">
          <input
            ref={fileRef}
            type="file"
            accept=".txt,.md,.mdx,.csv,.pdf,.docx,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            className="hidden"
            onChange={(e) => void onPickFile(e.target.files?.[0] ?? null)}
          />
          <Button
            type="button"
            variant="secondary"
            disabled={!wsId || uploading}
            onClick={() => fileRef.current?.click()}
          >
            {uploading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Uploading…
              </>
            ) : (
              <>
                <FileUp className="mr-2 h-4 w-4" />
                Choose file
              </>
            )}
          </Button>
          {uploadMsg ? (
            <p
              className={cn(
                "rounded-lg px-3 py-2 text-xs animate-fade-in",
                /fail|error|❌/i.test(uploadMsg)
                  ? "border border-destructive/30 bg-destructive/10 text-destructive"
                  : "border border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
              )}
              role="status"
            >
              {uploadMsg}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card className="gap-6 py-6">
        <CardHeader className="px-6">
          <CardTitle className="text-lg">Add from URL</CardTitle>
          <CardDescription className="text-[13px] leading-relaxed">
            Paste a web page URL — Flow fetches and indexes the main content.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 px-6">
          <div className="flex gap-2">
            <Input
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="https://example.com/article"
              className="flex-1 text-sm"
              onKeyDown={(e) => {
                if (e.key === "Enter" && wsId && urlInput.trim() && !crawling) void crawl();
              }}
            />
            <Button
              type="button"
              variant="secondary"
              disabled={!wsId || !urlInput.trim() || crawling}
              onClick={() => void crawl()}
            >
              {crawling ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Fetching…
                </>
              ) : (
                "Add URL"
              )}
            </Button>
          </div>
          {crawlMsg ? (
            <p
              className={cn(
                "rounded-lg px-3 py-2 text-xs animate-fade-in",
                /fail|error|❌/i.test(crawlMsg)
                  ? "border border-destructive/30 bg-destructive/10 text-destructive"
                  : "border border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
              )}
              role="status"
            >
              {crawlMsg}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card className="gap-6 py-6">
        <CardHeader className="px-6">
          <CardTitle className="text-lg">Add from text</CardTitle>
          <CardDescription className="text-[13px] leading-relaxed">
            Markdown or plain text. Same embedding pipeline as file upload.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 px-6">
          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="body">Body</Label>
            <Textarea id="body" value={body} onChange={(e) => setBody(e.target.value)} rows={8} className="min-h-[160px]" />
          </div>
          <Button onClick={() => void ingest()} disabled={!wsId || !body.trim() || ingesting}>
            {ingesting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Ingesting…
              </>
            ) : (
              "Ingest"
            )}
          </Button>
          {msg ? <p className="text-muted-foreground text-sm">{msg}</p> : null}
        </CardContent>
      </Card>

      <Card className="gap-6 py-6">
        <CardHeader className="px-6">
          <CardTitle className="text-lg">Sources</CardTitle>
          <CardDescription className="text-[13px] leading-relaxed">
            Click a source to preview its indexed chunks. Ingest status updates when embedding finishes.
          </CardDescription>
        </CardHeader>
        <CardContent className="px-6">
          {loadingSources ? (
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              Loading sources…
            </div>
          ) : sources.length === 0 ? (
            <EmptyState
              icon={BookOpenCheck}
              tone="brand"
              title="No sources yet"
              description="Upload a README or paste a short doc — then run an agent with Knowledge search enabled."
              action={
                <Button type="button" variant="secondary" onClick={() => router.push("/run")}>
                  Go to Run
                </Button>
              }
            />
          ) : (
            <>
              <style>{`@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }`}</style>
              <ul className="space-y-2 text-sm">
              {sources.map((s, i) => (
                <li
                  key={s.id}
                  className="flex items-center gap-2"
                  style={{
                    opacity: 0,
                    animation: `fadeIn 280ms ease-out forwards`,
                    animationDelay: `${i * 40}ms`,
                  }}
                >
                  <button
                    type="button"
                    className={cn(
                      "group flex-1 flex flex-col gap-2 rounded-xl border border-flow-800 bg-card px-4 py-3 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-flow-violet/50 hover:bg-flow-violet/[0.04] hover:shadow-md sm:flex-row sm:items-center sm:justify-between",
                      selectedSource?.id === s.id && "border-flow-violet/50 bg-flow-violet/[0.06]",
                    )}
                    onClick={() => setSelectedSource(s)}
                    aria-label={`View chunks for ${s.title}`}
                  >
                    <div className="min-w-0">
                      <span className="font-medium text-foreground">{s.title}</span>
                      <p className="text-muted-foreground text-xs">
                        {new Date(s.created_at).toLocaleString()} · {s.chunk_count ?? 0} chunks
                      </p>
                      {s.ingest_error ? (
                        <p className="text-destructive text-xs">{s.ingest_error}</p>
                      ) : null}
                    </div>
                    <Badge variant={statusVariant(s.ingest_status)} className="w-fit shrink-0 capitalize">
                      {s.ingest_status ?? "indexed"}
                    </Badge>
                  </button>
                  <button
                    type="button"
                    disabled={deletingId === s.id}
                    onClick={() => void deleteSource(s.id, s.title)}
                    aria-label={`Delete ${s.title}`}
                    className="flex-shrink-0 rounded-lg p-2 text-flow-600 transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-40"
                  >
                    {deletingId === s.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </button>
                </li>
              ))}
            </ul>
            {hasMoreSources && (
              <button
                type="button"
                onClick={() => void loadMoreSources()}
                disabled={loadingMoreSources}
                className="mt-3 mx-auto flex items-center gap-2 rounded-md border border-flow-800 bg-flow-900 px-4 py-2 font-mono text-xs text-flow-300 transition-colors hover:bg-flow-800 hover:text-flow-100 disabled:opacity-50"
              >
                {loadingMoreSources && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {loadingMoreSources ? "Loading…" : "Load more"}
              </button>
            )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
