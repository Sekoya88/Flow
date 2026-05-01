"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, BookOpen, FileUp, Loader2, Sparkles } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, apiFetch } from "@/lib/api";
import { track } from "@/lib/analytics";
import { getToken } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";

type Me = { workspaces: { id: string }[] };

type SourceRow = {
  id: string;
  title: string;
  created_at: string;
  chunk_count?: number;
  ingest_status?: string;
  ingest_error?: string;
};

type Sources = { sources: SourceRow[] };

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
  onClose,
}: {
  source: SourceRow | null;
  wsId: string;
  onClose: () => void;
}) {
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

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

  return (
    <Sheet open={source !== null} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="flex w-[min(100vw-1rem,32rem)] flex-col gap-0 sm:max-w-lg">
        <SheetHeader className="border-b border-border/60 pb-4 text-left">
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
                  className="rounded-lg border border-border/50 bg-muted/10 px-3 py-2.5"
                >
                  <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60">
                    Chunk {c.index + 1}
                  </p>
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

  const loadSources = useCallback(async (id: string) => {
    setLoadingSources(true);
    setListErr(null);
    try {
      const r = await apiFetch<Sources>(`/api/v1/knowledge?workspace_id=${id}`);
      setSources(r.sources);
      track("knowledge_list_viewed", { count: r.sources.length });
    } catch (e) {
      setListErr(e instanceof ApiError ? `${e.status}: ${e.body}` : String(e));
    } finally {
      setLoadingSources(false);
    }
  }, []);

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
    setMsg(null);
    setUploading(true);
    try {
      const fd = new FormData();
      fd.set("workspace_id", wsId);
      fd.set("file", f);
      await apiFetch("/api/v1/knowledge/upload", { method: "POST", body: fd });
      await loadSources(wsId);
      setMsg(`Uploaded "${f.name}".`);
      track("knowledge_upload", { workspace_id: wsId, filename: f.name });
    } catch (e) {
      setMsg(e instanceof ApiError ? `${e.status}: ${e.body}` : String(e));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
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
          onClose={() => setSelectedSource(null)}
        />
      )}

      <FlowPageHeader
        title="Knowledge"
        description="Sources are chunked and embedded for retrieval during runs. Upload small text files or paste content manually."
        meta={
          <Link
            href="/run"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }), "inline-flex w-fit items-center gap-1.5")}
          >
            <Sparkles className="h-3.5 w-3.5" aria-hidden />
            Back to Run
          </Link>
        }
      />

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

      <Card className="gap-6 py-6 shadow-sm">
        <CardHeader className="px-6">
          <CardTitle className="text-lg">Upload file</CardTitle>
          <CardDescription className="text-[13px] leading-relaxed">
            <code className="text-foreground/80">.txt</code>, <code className="text-foreground/80">.md</code>,{" "}
            <code className="text-foreground/80">.mdx</code>, or <code className="text-foreground/80">.csv</code> — max
            512KB. Requires OpenAI key on the API for embeddings.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 px-6">
          <input
            ref={fileRef}
            type="file"
            accept=".txt,.md,.mdx,.csv,text/plain,text/markdown"
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
        </CardContent>
      </Card>

      <Card className="gap-6 py-6 shadow-sm">
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

      <Card className="gap-6 py-6 shadow-sm">
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
            <div className="rounded-lg border border-dashed border-border/80 bg-muted/10 px-4 py-8 text-center">
              <p className="text-muted-foreground text-sm">
                No sources yet. Upload a README or paste a short doc — then run an agent with{" "}
                <strong className="text-foreground">Knowledge search</strong> enabled.
              </p>
              <Button type="button" className="mt-4" variant="secondary" onClick={() => router.push("/run")}>
                Go to Run
              </Button>
            </div>
          ) : (
            <>
              <style>{`@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }`}</style>
              <ul className="space-y-2 text-sm">
              {sources.map((s, i) => (
                <li key={s.id}>
                  <button
                    type="button"
                    className={cn(
                      "w-full flex flex-col gap-2 rounded-lg border border-border/60 bg-muted/5 px-3 py-3 text-left transition-colors hover:bg-muted/20 sm:flex-row sm:items-center sm:justify-between",
                      selectedSource?.id === s.id && "border-[var(--color-flow-brand)]/40 bg-[var(--color-flow-brand)]/5",
                    )}
                    style={{
                      opacity: 0,
                      animation: `fadeIn 280ms ease-out forwards`,
                      animationDelay: `${i * 40}ms`,
                    }}
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
                </li>
              ))}
            </ul>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
