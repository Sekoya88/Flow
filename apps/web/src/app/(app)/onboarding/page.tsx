"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { BookOpen, Globe, Loader2, Sparkles, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, apiFetch } from "@/lib/api";
import { track } from "@/lib/analytics";
import { getToken } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";

type Me = { workspaces: { id: string; name: string }[] };

type UseCase = "documents" | "automation" | "code";

const USE_CASES: { id: UseCase; label: string; desc: string; icon: React.ReactNode }[] = [
  {
    id: "documents",
    label: "Ask questions about my documents",
    desc: "Upload PDFs, notes, or articles — then query them with cited answers.",
    icon: <BookOpen className="h-5 w-5" aria-hidden />,
  },
  {
    id: "automation",
    label: "Run automated tasks",
    desc: "Schedule recurring agent pipelines over your knowledge base.",
    icon: <Sparkles className="h-5 w-5" aria-hidden />,
  },
  {
    id: "code",
    label: "Write & execute code",
    desc: "Ask an agent to write Python, run it in a sandbox, and return results.",
    icon: <Globe className="h-5 w-5" aria-hidden />,
  },
];

export default function OnboardingPage() {
  const router = useRouter();
  const routerRef = useRef(router);
  const fileRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<1 | 2>(1);
  const [useCase, setUseCase] = useState<UseCase>("documents");
  const [wsId, setWsId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  useEffect(() => {
    routerRef.current = router;
  }, [router]);

  useEffect(() => {
    if (!getToken()) {
      routerRef.current.replace("/login");
      return;
    }
    apiFetch<Me>("/api/v1/auth/me")
      .then((m) => {
        const w = m.workspaces?.[0];
        if (!w) { setLoadErr("No workspace for this account."); return; }
        setWsId(w.id);
        track("onboarding_viewed", {});
      })
      .catch(() => setLoadErr("Could not load account."));
  }, []);

  async function onPickFile(f: File | null) {
    if (!f || !wsId) return;
    setMsg(null);
    setUploading(true);
    try {
      const fd = new FormData();
      fd.set("workspace_id", wsId);
      fd.set("file", f);
      await apiFetch("/api/v1/knowledge/upload", { method: "POST", body: fd });
      track("onboarding_first_doc_uploaded", { filename: f.name });
      router.push("/run");
    } catch (e) {
      setMsg(e instanceof ApiError ? `${e.status}: ${e.body}` : String(e));
      setUploading(false);
    }
    if (fileRef.current) fileRef.current.value = "";
  }

  if (loadErr) {
    return <p className="text-destructive text-sm p-4">{loadErr}</p>;
  }

  return (
    <div className="mx-auto max-w-xl space-y-8 pb-8">
      <FlowPageHeader
        leading={<BookOpen className="h-8 w-8 text-primary opacity-90" aria-hidden />}
        title={step === 1 ? "Welcome to Flow" : "Add your first document"}
        description={
          step === 1
            ? "What do you want to do with Flow?"
            : "Upload a PDF, .md, or .txt file to get started. Your agent is already configured."
        }
      />

      {step === 1 && (
        <div className="space-y-3">
          {USE_CASES.map((uc) => (
            <button
              key={uc.id}
              type="button"
              onClick={() => setUseCase(uc.id)}
              className={cn(
                "w-full flex items-start gap-4 rounded-xl border px-4 py-4 text-left transition-colors",
                useCase === uc.id
                  ? "border-primary/60 bg-primary/5"
                  : "border-flow-800 bg-background hover:bg-muted/20",
              )}
            >
              <span className={cn("mt-0.5 shrink-0", useCase === uc.id ? "text-primary" : "text-muted-foreground")}>
                {uc.icon}
              </span>
              <div>
                <p className="font-medium text-foreground text-sm">{uc.label}</p>
                <p className="text-muted-foreground text-xs mt-0.5 leading-relaxed">{uc.desc}</p>
              </div>
            </button>
          ))}

          <Button
            className="w-full mt-4"
            onClick={() => {
              track("onboarding_usecase_selected", { use_case: useCase });
              if (useCase === "documents") {
                setStep(2);
              } else {
                router.push("/run");
              }
            }}
          >
            Continue
          </Button>
          <Button variant="ghost" className="w-full text-muted-foreground text-sm" onClick={() => router.push("/dashboard")}>
            Skip for now
          </Button>
        </div>
      )}

      {step === 2 && (
        <Card className="shadow-sm">
          <CardHeader className="px-6">
            <CardTitle className="text-base">Upload a document</CardTitle>
            <CardDescription className="text-[13px] leading-relaxed">
              PDF, .md, .txt, or .docx — up to 20MB. Flow will chunk and embed it for retrieval.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 px-6 pb-6">
            <input
              ref={fileRef}
              type="file"
              accept=".txt,.md,.mdx,.pdf,.docx,text/plain,application/pdf"
              className="hidden"
              onChange={(e) => void onPickFile(e.target.files?.[0] ?? null)}
            />

            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={uploading || !wsId}
              className={cn(
                "w-full rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors",
                uploading
                  ? "border-primary/40 bg-primary/5 cursor-not-allowed"
                  : "border-flow-800 hover:border-primary/40 hover:bg-muted/10 cursor-pointer",
              )}
            >
              {uploading ? (
                <div className="flex flex-col items-center gap-2 text-primary">
                  <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
                  <span className="text-sm font-medium">Indexing…</span>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2 text-muted-foreground">
                  <Upload className="h-8 w-8" aria-hidden />
                  <span className="text-sm font-medium text-foreground">Click to choose a file</span>
                  <span className="text-xs">PDF, .md, .txt, .docx</span>
                </div>
              )}
            </button>

            {msg ? <p className="text-destructive text-sm">{msg}</p> : null}

            <div className="flex gap-2 pt-2">
              <Button variant="ghost" size="sm" onClick={() => setStep(1)} className="text-muted-foreground">
                Back
              </Button>
              <Button variant="outline" size="sm" className="ml-auto" onClick={() => router.push("/run")}>
                Skip — go to Run
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
