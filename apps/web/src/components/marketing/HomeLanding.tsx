import Link from "next/link";
import { ArrowRight, Brain, Layers, Zap } from "lucide-react";
import { FlowMark } from "@/components/brand/FlowLogo";
import { PublicHeader } from "@/components/layout/PublicHeader";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const pillars = [
  {
    label: "Layered",
    text: "FastAPI + LangGraph: clear boundaries, durable checkpoints.",
  },
  {
    label: "Observable",
    text: "Streamed runs, structured logs, and a dashboard you can trust.",
  },
  {
    label: "Grounded",
    text: "Workspace knowledge + preferences wired into every execution.",
  },
] as const;

export function HomeLanding() {
  return (
    <div className="flex min-h-screen flex-col">
      <PublicHeader />
      <main className="relative flex-1 animate-fade-in">
        <section className="mx-auto max-w-2xl px-5 pt-10 text-center md:max-w-3xl md:pt-14">
          <div
            className="flow-hero-surface mx-auto mb-6 flex h-14 w-14 items-center justify-center overflow-hidden animate-slide-up"
            aria-hidden
          >
            <FlowMark size={40} className="text-foreground" />
          </div>

          <h1 className="mb-4 animate-slide-up text-3xl font-semibold leading-tight tracking-tight md:text-4xl [animation-delay:60ms]">
            Run agents with clarity
          </h1>
          <p className="mb-8 animate-slide-up text-sm leading-relaxed text-muted-foreground md:text-[15px] [animation-delay:120ms]">
            Guided runs, workspace memory, and RAG — calm surfaces, grain, and a cyan-forward stream accent so live
            execution reads as motion, not noise.
          </p>

          <div className="flex flex-col items-center justify-center gap-3 animate-slide-up sm:flex-row [animation-delay:180ms]">
            <Link
              href="/register"
              className={cn(
                buttonVariants({ size: "lg" }),
                "inline-flex min-w-[10rem] items-center justify-center gap-2 px-6",
              )}
            >
              Get started
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link href="/login" className={cn(buttonVariants({ variant: "outline", size: "lg" }), "min-w-[10rem]")}>
              Sign in
            </Link>
          </div>

          <div className="mt-14 grid grid-cols-1 gap-3 text-left sm:grid-cols-3">
            {pillars.map((f, i) => (
              <div
                key={f.label}
                className="animate-slide-up rounded-lg border border-border/60 bg-card/30 p-3"
                style={{ animationDelay: `${240 + i * 60}ms` }}
              >
                <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  {f.label}
                </p>
                <p className="text-[12px] leading-snug text-foreground/90">{f.text}</p>
              </div>
            ))}
          </div>

          <div
            className="mx-auto mt-12 flex max-w-md flex-wrap items-center justify-center gap-6 text-muted-foreground animate-slide-up"
            style={{ animationDelay: "420ms" }}
          >
            <span className="flex items-center gap-2 text-xs">
              <Layers className="h-4 w-4 opacity-70" />
              Graph runs
            </span>
            <span className="flex items-center gap-2 text-xs">
              <Brain className="h-4 w-4 opacity-70" />
              Memory & prefs
            </span>
            <span className="flex items-center gap-2 text-xs">
              <Zap className="h-4 w-4 opacity-70" />
              SSE streams
            </span>
          </div>
        </section>
      </main>

      <footer className="relative mt-auto border-t border-border/40 py-4 text-center text-[10px] uppercase tracking-wide text-muted-foreground/60">
        Flow · agent platform · shadcn + Next.js
      </footer>
    </div>
  );
}
