import Link from "next/link";
import { ArrowRight, Brain, Layers, Zap } from "lucide-react";
import { FlowMark } from "@/components/brand/FlowLogo";
import { PublicHeader } from "@/components/layout/PublicHeader";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const pillars = [
  {
    icon: Layers,
    label: "Agentic Knowledge Graph",
    text: "Every execution, tool call, and retrieved document is automatically mapped into a knowledge graph powered by PageRank and semantic clustering.",
  },
  {
    icon: Brain,
    label: "Metacognition & Evaluation",
    text: "Automated LLM-as-a-judge pipelines. Golden Sets run against your agents hourly to detect regressions and propose structural fixes.",
  },
  {
    icon: Zap,
    label: "Zero-latency SSE",
    text: "Built on React 19 and raw Server-Sent Events. Token streaming uses zero-render DOM mutation for unparalleled text generation speed.",
  },
] as const;

export function HomeLanding() {
  return (
    <div className="flex min-h-screen flex-col overflow-x-hidden bg-flow-950">
      <PublicHeader />

      <main className="flex-1 pb-20">
        {/* HERO */}
        <section className="mx-auto grid max-w-[1200px] grid-cols-1 gap-8 px-4 pt-16 md:grid-cols-[1.1fr_0.9fr] lg:gap-12 lg:pt-24">
          <div className="flex flex-col justify-center">
            <p className="mb-4 font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-flow-amber">
              Flow Workspace
            </p>
            <h1 className="font-mono text-3xl font-bold tracking-tighter text-flow-50 lg:text-4xl">
              The cognitive layer<br />
              for your agents.
            </h1>
            <p className="mt-5 max-w-xl font-mono text-sm leading-relaxed text-flow-400">
              Open-source, highly observable agent platform. Build with FastAPI, LangGraph, and Next.js.
              Long-term memory, continuous evaluation, and deterministic streaming.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link href="/register" className={cn(buttonVariants({ size: "lg" }), "gap-2")}>
                Start building
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
              <Link href="/login" className={cn(buttonVariants({ variant: "outline", size: "lg" }))}>
                Sign in
              </Link>
            </div>

            <div className="mt-10 grid grid-cols-3 gap-3">
              {[
                { val: "< 120ms", lbl: "TTFB Stream" },
                { val: "O(1)", lbl: "Memory recall" },
                { val: "100%", lbl: "Type safe" },
              ].map((stat) => (
                <div key={stat.lbl} className="rounded-[6px] border border-flow-800 bg-flow-900 p-4">
                  <div className="font-mono text-xl font-bold text-flow-50">{stat.val}</div>
                  <div className="mt-1 font-mono text-[10px] font-medium uppercase tracking-[0.1em] text-flow-500">
                    {stat.lbl}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right: Code preview */}
          <div className="flex min-h-[320px] flex-col gap-3 rounded-[6px] border border-flow-800 bg-flow-900 p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 rounded-[4px] border border-flow-amber/30 bg-flow-amber/10 px-2.5 py-1">
                <div className="h-1.5 w-1.5 animate-pulse rounded-full bg-flow-amber" />
                <span className="font-mono text-[10px] font-medium text-flow-amber">Execution active</span>
              </div>
              <span className="font-mono text-[10px] text-flow-500">deer-flow / trace</span>
            </div>

            <div className="grid flex-1 grid-cols-2 gap-2">
              {[
                { lbl: "Routing", val: "Semantic Match" },
                { lbl: "Tool Calls", val: "pgvector_search" },
              ].map((item) => (
                <div key={item.lbl} className="rounded-[6px] border border-flow-800 bg-flow-950 p-3">
                  <dt className="font-mono text-[10px] uppercase tracking-[0.1em] text-flow-500">{item.lbl}</dt>
                  <dd className="mt-1 font-mono text-xs font-semibold text-flow-100">{item.val}</dd>
                </div>
              ))}
              <div className="col-span-2 rounded-[6px] border border-flow-800 bg-flow-950 p-3">
                <dt className="mb-2 font-mono text-[10px] uppercase tracking-[0.1em] text-flow-500">Streaming Output</dt>
                <pre className="font-mono text-[11px] leading-relaxed text-flow-300">
                  <code>
{`import { Memory } from "flow-core";
// Autonomous context resolution
await agent.reflect(state);`}
                  </code>
                </pre>
              </div>
            </div>
          </div>
        </section>

        {/* FEATURE GRID */}
        <section className="mx-auto mt-10 grid max-w-[1200px] grid-cols-1 gap-3 px-4 md:grid-cols-3">
          {pillars.map(({ icon: Icon, label, text }) => (
            <div key={label} className="rounded-[6px] border border-flow-800 bg-flow-900 p-5">
              <Icon className="mb-3 h-5 w-5 text-flow-amber" />
              <h3 className="mb-2 font-mono text-sm font-semibold tracking-tight text-flow-50">{label}</h3>
              <p className="font-mono text-xs leading-relaxed text-flow-400">{text}</p>
            </div>
          ))}
        </section>
      </main>

      <footer className="border-t border-flow-800 bg-flow-950 py-6 text-center">
        <div className="flex items-center justify-center gap-2 mb-1.5">
          <FlowMark size={20} className="text-flow-500" />
          <span className="font-mono text-xs font-medium text-flow-500">Flow Platform</span>
        </div>
        <p className="font-mono text-[10px] uppercase tracking-[0.08em] text-flow-700">
          Agent Workspace · FastAPI · Next.js · pgvector
        </p>
      </footer>
    </div>
  );
}
