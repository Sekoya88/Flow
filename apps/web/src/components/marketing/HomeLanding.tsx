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
    <div className="flex min-h-screen flex-col overflow-x-hidden">
      <PublicHeader />
      
      {/* Background elements */}
      <div className="pointer-events-none fixed inset-0 flow-grain opacity-[0.22]" aria-hidden />
      <div className="pointer-events-none fixed inset-x-0 top-0 h-[80vh] flow-ambient-mesh" aria-hidden />

      <main className="relative z-10 flex-1 animate-fade-in pb-20">
        {/* HERO BENTO */}
        <section className="mx-auto grid max-w-[1200px] grid-cols-1 gap-8 px-4 pt-10 md:grid-cols-[1.1fr_0.9fr] lg:gap-10 lg:pt-20">
          
          {/* Left: Copy & Stats */}
          <div className="flex flex-col justify-center">
            <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.14em] text-flow-brand animate-slide-up">
              Flow Workspace
            </p>
            <h1 className="text-display animate-slide-up [animation-delay:60ms]">
              The cognitive layer <br />
              <span className="text-brand-gradient">for your agents.</span>
            </h1>
            <p className="mt-5 max-w-xl text-body-lg text-muted-foreground animate-slide-up [animation-delay:120ms]">
              Flow is an open-source, highly observable agent platform. Build with FastAPI, LangGraph, and Next.js. 
              Features long-term memory, continuous evaluation, and deterministic streaming.
            </p>
            
            <div className="mt-8 flex flex-wrap items-center gap-3 animate-slide-up [animation-delay:180ms]">
              <Link href="/register" className={cn(buttonVariants({ size: "lg" }), "gap-2 px-6 shadow-xl shadow-flow-brand/20")}>
                Start building
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link href="/login" className={cn(buttonVariants({ variant: "outline", size: "lg" }), "bg-background/50 backdrop-blur-md")}>
                Sign in
              </Link>
            </div>

            {/* Stats Strip */}
            <div className="mt-10 grid grid-cols-3 gap-3 animate-slide-up [animation-delay:240ms]">
              {[
                { val: "< 120ms", lbl: "TTFB Stream" },
                { val: "O(1)", lbl: "Memory recall" },
                { val: "100%", lbl: "Type safe" },
              ].map((stat) => (
                <div key={stat.lbl} className="rounded-xl border border-border/60 bg-card/40 p-4 backdrop-blur-md">
                  <div className="text-xl font-semibold tracking-tight lg:text-2xl">{stat.val}</div>
                  <div className="mt-1 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                    {stat.lbl}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right: Code/Graph Preview */}
          <div className="flow-hero-surface flex min-h-[340px] flex-col gap-3 p-5 animate-slide-up [animation-delay:200ms]">
            <div className="flex items-center justify-between text-[11px] text-muted-foreground">
              <div className="flex items-center gap-2">
                <div className="flex h-6 items-center gap-1.5 rounded-full border border-flow-brand/30 bg-flow-brand/10 px-3 font-mono text-[10px] text-flow-brand">
                  <div className="h-1.5 w-1.5 animate-pulse rounded-full bg-flow-brand" />
                  Execution active
                </div>
              </div>
              <span className="font-mono">deer-flow / trace</span>
            </div>
            
            <div className="grid flex-1 grid-cols-2 gap-3">
              <div className="flex flex-col gap-2 rounded-xl border border-border/50 bg-background/60 p-4">
                <dt className="text-[10px] uppercase tracking-widest text-muted-foreground">Routing</dt>
                <dd className="font-mono text-sm font-semibold">Semantic Match</dd>
              </div>
              <div className="flex flex-col gap-2 rounded-xl border border-border/50 bg-background/60 p-4">
                <dt className="text-[10px] uppercase tracking-widest text-muted-foreground">Tool Calls</dt>
                <dd className="font-mono text-sm font-semibold">pgvector_search</dd>
              </div>
              <div className="col-span-2 flex flex-col gap-2 rounded-xl border border-border/50 bg-background/60 p-4">
                <dt className="text-[10px] uppercase tracking-widest text-muted-foreground">Streaming Output</dt>
                <dd className="font-mono text-xs leading-relaxed text-foreground/90">
                  <span className="text-flow-brand">import</span> {"{ Memory }"} <span className="text-flow-brand">from</span> "flow-core";<br/>
                  <span className="text-muted-foreground">{'// Autonomous context resolution'}</span><br/>
                  await agent.reflect(state);
                </dd>
              </div>
            </div>
          </div>
        </section>

        {/* FEATURE BENTO GRID */}
        <section className="mx-auto mt-8 grid max-w-[1200px] grid-cols-1 gap-4 px-4 md:grid-cols-12">
          {/* Bento 1: Graph */}
          <div className="surface-glass flex min-h-[220px] flex-col gap-3 rounded-2xl p-6 md:col-span-7 animate-slide-up [animation-delay:300ms]">
            <Layers className="h-6 w-6 text-flow-brand" />
            <h3 className="text-lg font-semibold tracking-tight">Agentic Knowledge Graph</h3>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Every execution, tool call, and retrieved document is automatically mapped into a highly 
              performant 3D knowledge graph powered by PageRank and semantic clustering.
            </p>
          </div>

          {/* Bento 2: Metacognition */}
          <div className="surface-glass flex min-h-[220px] flex-col gap-3 rounded-2xl p-6 md:col-span-5 animate-slide-up [animation-delay:360ms]">
            <Brain className="h-6 w-6 text-flow-brand" />
            <h3 className="text-lg font-semibold tracking-tight">Metacognition & Evaluation</h3>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Automated LLM-as-a-judge pipelines. Golden Sets run against your agents hourly to detect 
              regressions and autonomously propose structural Skill fixes.
            </p>
          </div>

          {/* Bento 3: Streaming */}
          <div className="flow-hero-surface flex min-h-[220px] flex-col gap-3 rounded-2xl p-6 md:col-span-4 animate-slide-up [animation-delay:420ms]">
            <Zap className="h-6 w-6 text-flow-brand" />
            <h3 className="text-lg font-semibold tracking-tight">Zero-latency SSE</h3>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Built on React 19 and raw Server-Sent Events. Token streaming uses zero-render DOM mutation 
              for unparalleled text generation speed.
            </p>
          </div>

          {/* Bento 4: Code Block */}
          <div className="surface-glass flex min-h-[220px] flex-col rounded-2xl p-6 md:col-span-8 animate-slide-up [animation-delay:480ms]">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold tracking-tight">Extensible Python Backend</h3>
              <span className="font-mono text-[10px] text-flow-brand">pip install flow</span>
            </div>
            <div className="mt-auto overflow-hidden rounded-xl border border-border/50 bg-black/80 p-4">
              <pre className="font-mono text-[11px] text-zinc-300">
                <code>
<span className="text-pink-400">@tool</span>
<span className="text-purple-400">async def</span> <span className="text-blue-300">analyze_repository</span>(repo_url: <span className="text-teal-300">str</span>):<br/>
    <span className="text-zinc-500">"""Clone and analyze architecture."""</span><br/>
    <span className="text-purple-400">return await</span> agent.spawn_worker(...)
                </code>
              </pre>
            </div>
          </div>
        </section>
      </main>

      <footer className="relative mt-auto border-t border-border/40 bg-background/50 py-8 text-center backdrop-blur-md">
        <div className="flex items-center justify-center gap-2 mb-2">
          <FlowMark size={16} className="text-muted-foreground" />
          <span className="font-semibold text-muted-foreground text-sm">Flow Platform</span>
        </div>
        <p className="text-[11px] tracking-wide text-muted-foreground/60">
          Agent Workspace &middot; FastAPI &middot; Next.js &middot; pgvector
        </p>
      </footer>
    </div>
  );
}
