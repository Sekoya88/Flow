"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, CheckCircle2, ExternalLink, Eye, GitBranch, Loader2, ShieldAlert, Sparkles, XCircle } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { toast } from "sonner";
import { ApiError, apiFetch } from "@/lib/api";
import { track } from "@/lib/analytics";
import { getToken } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { SkillDiffView } from "@/components/agents/SkillDiffView";

type ProposalRow = {
  id: string;
  title: string;
  body: string;
  status: string;
  created_at: string;
  execution_id?: string;
  auto_approved?: boolean;
};

/* Structured metadata embedded as JSON in proposal bodies (regression gate,
   skill improvements). Plain-text bodies return null. */
type ProposalMeta = {
  kind?: string;
  skill_candidate_id?: string;
  skill_id?: string;
  run_id?: string;
  epoch?: number;
  reason?: string;
  summary?: string;
};

function parseProposalMeta(body: string): ProposalMeta | null {
  if (!body.trim().startsWith("{")) return null;
  try {
    const meta = JSON.parse(body) as ProposalMeta;
    return typeof meta === "object" && meta !== null ? meta : null;
  } catch {
    return null;
  }
}

function isRegressionGate(meta: ProposalMeta | null): boolean {
  return meta?.kind === "regression_gate" || (!!meta?.skill_candidate_id && !!meta?.reason);
}

/* Fetches candidate + currently-active skill content and renders the diff. */
function CandidateDiff({ candidateId }: { candidateId: string }) {
  const [state, setState] = useState<
    | { phase: "loading" }
    | { phase: "error"; message: string }
    | { phase: "ready"; oldContent: string; newContent: string; oldLabel: string; newLabel: string }
  >({ phase: "loading" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const candidate = await apiFetch<{ agent_id: string; name: string; content_md: string; version: number }>(
          `/api/v1/skills/${candidateId}`,
        );
        const history = await apiFetch<{ versions: Array<{ content_md: string; active: boolean; version: number }> }>(
          `/api/v1/skills/history?agent_id=${candidate.agent_id}&name=${encodeURIComponent(candidate.name)}`,
        );
        const active = history.versions.find((v) => v.active);
        if (cancelled) return;
        setState({
          phase: "ready",
          oldContent: active?.content_md ?? "",
          newContent: candidate.content_md,
          oldLabel: active ? `v${active.version} (active)` : "(no active version)",
          newLabel: `v${candidate.version} (candidate)`,
        });
      } catch (e) {
        if (!cancelled) {
          setState({ phase: "error", message: e instanceof ApiError ? `${e.status}: ${e.body}` : String(e) });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [candidateId]);

  if (state.phase === "loading") {
    return (
      <div className="flex items-center gap-2 p-4 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading skill diff…
      </div>
    );
  }
  if (state.phase === "error") {
    return <p className="p-4 font-mono text-xs text-destructive">Could not load diff: {state.message}</p>;
  }
  return (
    <div className="p-4">
      <div className="mb-2 flex items-center gap-1.5">
        <GitBranch className="h-3 w-3 text-flow-violet" />
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          Candidate vs active skill
        </span>
      </div>
      <SkillDiffView
        oldContent={state.oldContent}
        newContent={state.newContent}
        oldLabel={state.oldLabel}
        newLabel={state.newLabel}
      />
    </div>
  );
}

type Props = { proposals: ProposalRow[] };

function statusConfig(status: string) {
  switch (status) {
    case "pending":
      return {
        label: "Pending",
        className: "border-[var(--color-flow-thinking)]/40 bg-[var(--color-flow-thinking)]/10 text-[var(--color-flow-thinking)]",
        icon: Sparkles,
      };
    case "approved":
      return {
        label: "Approved",
        className: "border-[var(--color-flow-done)]/40 bg-[var(--color-flow-done)]/10 text-[var(--color-flow-done)]",
        icon: CheckCircle2,
      };
    case "rejected":
      return {
        label: "Rejected",
        className: "border-flow-800 bg-muted/20 text-muted-foreground",
        icon: XCircle,
      };
    default:
      return { label: status, className: "border-flow-800 bg-muted/20 text-muted-foreground", icon: Sparkles };
  }
}

export default function ProposalsPage() {
  const router = useRouter();
  const routerRef = useRef(router);
  const [rows, setRows] = useState<ProposalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [actionId, setActionId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ProposalRow | null>(null);
  const [confirm, setConfirm] = useState<{ id: string; status: "approved" | "rejected" } | null>(null);

  const load = useCallback(async () => {
    setLoadErr(null);
    setLoading(true);
    try {
      const r = await apiFetch<Props>("/api/v1/proposals");
      setRows(r.proposals);
    } catch (e) {
      setLoadErr(e instanceof ApiError ? `${e.status}: ${e.body}` : String(e));
    } finally {
      setLoading(false);
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
    void load();
  }, [load]);

  async function act(id: string, status: "approved" | "rejected") {
    setActionId(id);
    try {
      await apiFetch(`/api/v1/proposals/${id}/action`, { method: "POST", json: { status } });
      if (status === "approved") track("proposal_applied", { proposal_id: id });
      else track("proposal_discarded", { proposal_id: id });
      toast.success(status === "approved" ? "Proposal approved" : "Proposal rejected");
      await load();
      setConfirm(null);
    } catch (e) {
      setLoadErr(e instanceof ApiError ? `${e.status}: ${e.body}` : String(e));
      toast.error("Action failed");
    } finally {
      setActionId(null);
    }
  }

  function openDetail(p: ProposalRow) {
    setDetail(p);
    track("proposal_viewed", { proposal_id: p.id, status: p.status });
  }

  const pending = rows.filter((r) => r.status === "pending");
  const resolved = rows.filter((r) => r.status !== "pending");

  return (
    <div className="mx-auto max-w-3xl space-y-8 pb-8 animate-fade-in">
      <FlowPageHeader
        title="Proposals"
        titleSuffix={
          pending.length > 0 ? (
            <Badge
              variant="outline"
              className="h-6 rounded-full border-[var(--color-flow-thinking)]/40 bg-[var(--color-flow-thinking)]/10 px-2.5 text-xs text-[var(--color-flow-thinking)]"
            >
              {pending.length} pending
            </Badge>
          ) : null
        }
        description="Curator suggestions from low run scores. Review the text, then approve or reject."
      />

      {/* Detail sheet */}
      <Sheet open={detail !== null} onOpenChange={(o) => !o && setDetail(null)}>
        <SheetContent side="right" className="flex w-[min(100vw-1rem,28rem)] flex-col gap-0 sm:max-w-md">
          <SheetHeader className="border-b border-flow-800 pb-4 text-left">
            <SheetTitle className="pr-8">{detail?.title ?? "Proposal"}</SheetTitle>
            <SheetDescription className="text-left">
              {detail ? (
                <>
                  <span className="capitalize">{detail.status}</span>
                  {" · "}
                  {new Date(detail.created_at).toLocaleString()}
                  {detail.execution_id ? (
                    <>
                      {" · "}
                      <Link
                        href={`/run#exec-${detail.execution_id}`}
                        className="inline-flex items-center gap-1 font-medium text-foreground underline-offset-4 hover:underline"
                        onClick={() => setDetail(null)}
                      >
                        Linked run
                        <ExternalLink className="h-3 w-3 opacity-70" aria-hidden />
                      </Link>
                    </>
                  ) : null}
                </>
              ) : null}
            </SheetDescription>
          </SheetHeader>
          <div className="min-h-[12rem] flex-1 overflow-y-auto px-1">
            {(() => {
              const meta = detail ? parseProposalMeta(detail.body) : null;
              if (meta && isRegressionGate(meta)) {
                return (
                  <div>
                    <div className="m-4 mb-0 rounded-lg border border-red-500/30 bg-red-500/5 p-3 space-y-1.5">
                      <div className="flex items-center gap-1.5">
                        <ShieldAlert className="h-3.5 w-3.5 text-red-400" />
                        <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-red-400">
                          Regression gate
                        </span>
                        {meta.epoch != null && (
                          <span className="font-mono text-[10px] text-muted-foreground">epoch {meta.epoch}</span>
                        )}
                      </div>
                      {meta.reason && (
                        <p className="font-mono text-xs leading-relaxed text-red-300/90">{meta.reason}</p>
                      )}
                      {meta.summary && (
                        <p className="text-xs leading-relaxed text-muted-foreground">{meta.summary}</p>
                      )}
                    </div>
                    {meta.skill_candidate_id && <CandidateDiff candidateId={meta.skill_candidate_id} />}
                  </div>
                );
              }
              return (
                <pre className="whitespace-pre-wrap wrap-break-word p-4 font-mono text-xs leading-relaxed">
                  {detail?.body ?? ""}
                </pre>
              );
            })()}
          </div>
          {detail?.status === "pending" ? (
            <div className="border-t border-flow-800 p-4 flex gap-2">
              <Button
                size="sm"
                disabled={actionId !== null}
                onClick={() => { setDetail(null); setConfirm({ id: detail.id, status: "approved" }); }}
              >
                Approve…
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={actionId !== null}
                onClick={() => { setDetail(null); setConfirm({ id: detail.id, status: "rejected" }); }}
              >
                Reject…
              </Button>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>

      {/* Confirm dialog */}
      <AlertDialog open={confirm !== null} onOpenChange={(o) => !o && setConfirm(null)}>
        <AlertDialogContent className="max-w-md sm:max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirm?.status === "approved" ? "Approve proposal?" : "Reject proposal?"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirm?.status === "approved"
                ? "This marks the proposal as approved. You can still review history from the list."
                : "This marks the proposal as rejected and removes it from the pending queue."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={actionId !== null}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={confirm === null || actionId !== null}
              variant={confirm?.status === "rejected" ? "outline" : "default"}
              onClick={(e) => {
                e.preventDefault();
                if (!confirm) return;
                void act(confirm.id, confirm.status);
              }}
            >
              {actionId && confirm && actionId === confirm.id ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Working…
                </>
              ) : confirm?.status === "approved" ? (
                "Approve"
              ) : (
                "Reject"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {loadErr ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Could not load proposals</AlertTitle>
          <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <span>{loadErr}</span>
            <Button type="button" size="sm" variant="outline" onClick={() => void load()}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      <style>{`@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }`}</style>

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground text-sm">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Loading proposals…
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border/80 bg-muted/10 px-4 py-12 text-center">
          <Sparkles className="mx-auto mb-3 h-8 w-8 text-muted-foreground/40" aria-hidden />
          <p className="text-muted-foreground text-sm">
            No proposals yet. When a run scores low, the curator may suggest changes here.
          </p>
          <Button type="button" className="mt-4" variant="secondary" onClick={() => router.push("/run")}>
            Go to Run
          </Button>
        </div>
      ) : (
        <div className="space-y-10">
          {pending.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Pending review
              </h2>
              <div className="space-y-3">
                {pending.map((p, i) => (
                  <ProposalCard
                    key={p.id}
                    proposal={p}
                    animDelay={i * 60}
                    actionId={actionId}
                    onDetail={openDetail}
                    onConfirm={setConfirm}
                  />
                ))}
              </div>
            </section>
          )}

          {resolved.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Resolved
              </h2>
              <div className="space-y-3 opacity-70 transition-opacity hover:opacity-100">
                {resolved.map((p, i) => (
                  <ProposalCard
                    key={p.id}
                    proposal={p}
                    animDelay={(pending.length + i) * 60}
                    actionId={actionId}
                    onDetail={openDetail}
                    onConfirm={setConfirm}
                  />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}

function ProposalCard({
  proposal: p,
  animDelay,
  actionId,
  onDetail,
  onConfirm,
}: {
  proposal: ProposalRow;
  animDelay: number;
  actionId: string | null;
  onDetail: (p: ProposalRow) => void;
  onConfirm: (c: { id: string; status: "approved" | "rejected" }) => void;
}) {
  const cfg = statusConfig(p.status);
  const StatusIcon = cfg.icon;
  const meta = parseProposalMeta(p.body);
  const gate = isRegressionGate(meta);
  const preview = meta ? (meta.summary ?? meta.reason ?? p.title) : p.body;

  return (
    <Card
      className="group flow-card border-flow-800 transition-all duration-200 hover:-translate-y-0.5 hover:border-flow-violet/50 hover:shadow-md hover:shadow-none/5"
      style={{
        opacity: 0,
        animation: `fadeIn 320ms ease-out forwards`,
        animationDelay: `${animDelay}ms`,
      }}
    >
      <CardHeader className="pb-2 pt-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1">
            <CardTitle className="text-base leading-snug">{p.title}</CardTitle>
            <CardDescription className="text-xs">
              {new Date(p.created_at).toLocaleString()}
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {gate && (
              <Badge
                variant="outline"
                className="w-fit shrink-0 gap-1 text-xs font-medium border-red-500/40 bg-red-500/10 text-red-400"
              >
                <ShieldAlert className="h-3 w-3" aria-hidden />
                Regression gate
              </Badge>
            )}
            {p.auto_approved && (
              <Badge
                variant="outline"
                className="w-fit shrink-0 gap-1 text-xs font-medium border-flow-violet/40 bg-flow-violet/10 text-flow-violet"
              >
                <Sparkles className="h-3 w-3" aria-hidden />
                Auto-approved
              </Badge>
            )}
            <Badge
              variant="outline"
              className={cn("w-fit shrink-0 gap-1 text-xs font-medium capitalize", cfg.className)}
            >
              <StatusIcon className="h-3 w-3" aria-hidden />
              {cfg.label}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pb-4">
        <p className="line-clamp-3 text-sm whitespace-pre-wrap text-muted-foreground">{preview}</p>
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="secondary" onClick={() => onDetail(p)}>
            <Eye className="mr-1.5 h-3.5 w-3.5" aria-hidden />
            Details
          </Button>
          {p.execution_id ? (
            <Link
              href={`/run#exec-${p.execution_id}`}
              className={cn(
                buttonVariants({ variant: "outline", size: "sm" }),
                "inline-flex items-center gap-1.5",
              )}
            >
              Run
              <ExternalLink className="h-3 w-3 opacity-70" aria-hidden />
            </Link>
          ) : null}
          {p.status === "pending" ? (
            <>
              <Button
                size="sm"
                disabled={actionId !== null}
                onClick={() => onConfirm({ id: p.id, status: "approved" })}
              >
                Approve…
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={actionId !== null}
                onClick={() => onConfirm({ id: p.id, status: "rejected" })}
              >
                Reject…
              </Button>
            </>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
