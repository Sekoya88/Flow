"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BookOpen, Check, Circle, Loader2, Sparkles } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, apiFetch } from "@/lib/api";
import { track } from "@/lib/analytics";
import { getToken } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Me = { workspaces: { id: string; name: string }[] };

const STORAGE_KEY = "flow.onboarding.steps.v1";

const STEPS: {
  id: string;
  title: string;
  description: string;
  href: string;
  cta: string;
}[] = [
  {
    id: "agent",
    title: "Pick an agent",
    description: "Open Run, choose an agent template, set display name and capabilities (knowledge, sandbox, memory).",
    href: "/run",
    cta: "Open Run",
  },
  {
    id: "knowledge",
    title: "Add knowledge",
    description: "Upload a small .txt/.md file or paste a doc so retrieval can ground answers.",
    href: "/knowledge",
    cta: "Open Knowledge",
  },
  {
    id: "run",
    title: "Launch a test run",
    description: "Send a short prompt, wait for the stream to finish, then skim the pipeline steps.",
    href: "/run",
    cta: "Run a prompt",
  },
  {
    id: "proposals",
    title: "Watch proposals",
    description: "After low-score runs, review curator suggestions — approve or reject with confirmation.",
    href: "/proposals",
    cta: "Open Proposals",
  },
];

function loadDone(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as unknown;
    if (!Array.isArray(arr)) return new Set();
    return new Set(arr.filter((x) => typeof x === "string"));
  } catch {
    return new Set();
  }
}

function saveDone(s: Set<string>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...s]));
  } catch {
    /* quota */
  }
}

export default function OnboardingPage() {
  const router = useRouter();
  const routerRef = useRef(router);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<Set<string>>(new Set());

  useEffect(() => {
    setDone(loadDone());
  }, []);

  useEffect(() => {
    routerRef.current = router;
  }, [router]);

  useEffect(() => {
    if (!getToken()) {
      routerRef.current.replace("/login");
      return;
    }
    setLoading(true);
    apiFetch<Me>("/api/v1/auth/me")
      .then((m) => {
        if (!m.workspaces?.length) setErr("No workspace for this account.");
        track("onboarding_viewed", { workspace_count: m.workspaces.length });
      })
      .catch((e) => {
        setErr(e instanceof ApiError ? `${e.status}: ${e.body}` : "Could not load account.");
      })
      .finally(() => setLoading(false));
  }, []);

  const allDone = useMemo(() => STEPS.every((s) => done.has(s.id)), [done]);

  function toggle(id: string) {
    setDone((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      saveDone(next);
      track("onboarding_step_toggled", { step_id: id, completed: next.has(id) });
      return next;
    });
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground text-sm">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Loading…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8 pb-8">
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-primary">
          <BookOpen className="h-8 w-8 opacity-90" aria-hidden />
        </div>
        <h1 className="font-heading text-3xl font-semibold tracking-tight">Get started</h1>
        <p className="text-muted-foreground text-[15px] leading-relaxed">
          Short checklist to go from empty workspace to a grounded run. Progress is stored in this browser only.
        </p>
        {err ? <p className="text-destructive text-sm">{err}</p> : null}
      </div>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle className="text-lg">Checklist</CardTitle>
          <CardDescription className="text-[13px] leading-relaxed">
            Tap a row to mark done when you&apos;ve tried the step. Links open the relevant screen.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {STEPS.map((s, i) => {
            const checked = done.has(s.id);
            return (
              <div
                key={s.id}
                className={cn(
                  "flex gap-3 rounded-lg border px-3 py-3 transition-colors",
                  checked ? "border-border/40 bg-muted/15" : "border-border/60 bg-background",
                )}
              >
                <button
                  type="button"
                  onClick={() => toggle(s.id)}
                  className="mt-0.5 shrink-0 text-muted-foreground hover:text-foreground"
                  aria-pressed={checked}
                  aria-label={checked ? `Mark step ${i + 1} not done` : `Mark step ${i + 1} done`}
                >
                  {checked ? (
                    <Check className="h-5 w-5 text-primary" aria-hidden />
                  ) : (
                    <Circle className="h-5 w-5" aria-hidden />
                  )}
                </button>
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className="text-muted-foreground text-xs font-medium tabular-nums">Step {i + 1}</span>
                    <span className="font-medium text-foreground">{s.title}</span>
                  </div>
                  <p className="text-muted-foreground text-sm leading-relaxed">{s.description}</p>
                  <Link
                    href={s.href}
                    className={cn(buttonVariants({ variant: "secondary", size: "sm" }), "mt-2 inline-flex w-fit gap-1.5")}
                  >
                    <Sparkles className="h-3.5 w-3.5 opacity-80" aria-hidden />
                    {s.cta}
                  </Link>
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      {allDone ? (
        <p className="text-center text-muted-foreground text-sm">
          You&apos;ve checked every step. Ship a real task on{" "}
          <Link href="/run" className="font-medium text-foreground underline-offset-4 hover:underline">
            Run
          </Link>
          .
        </p>
      ) : null}

      <div className="flex flex-wrap justify-center gap-2">
        <Button type="button" variant="outline" onClick={() => router.push("/dashboard")}>
          Dashboard
        </Button>
        <Button type="button" onClick={() => router.push("/run")}>
          Go to Run
        </Button>
      </div>
    </div>
  );
}
