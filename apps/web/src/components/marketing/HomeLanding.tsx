import { Brain, Layers, Terminal, Zap } from "lucide-react";
import { FlowMark } from "@/components/brand/FlowLogo";
import { PublicHeader } from "@/components/layout/PublicHeader";
import { HeroCanvas } from "@/components/marketing/HeroCanvas";
import { EnterAppCta } from "@/components/marketing/EnterAppCta";

const pillars = [
  {
    icon: Layers,
    label: "Agentic Knowledge Graph",
    text: "Every execution, tool call, and retrieved document is automatically mapped into a knowledge graph powered by PageRank and semantic clustering.",
    accent: "from-flow-violet to-violet-500",
  },
  {
    icon: Brain,
    label: "Metacognition & Evaluation",
    text: "Automated LLM-as-a-judge pipelines. Golden Sets run against your agents hourly to detect regressions and propose structural fixes.",
    accent: "from-fuchsia-500 to-pink-500",
  },
  {
    icon: Zap,
    label: "Zero-latency SSE",
    text: "Built on React 19 and raw Server-Sent Events. Token streaming uses zero-render DOM mutation for unparalleled text generation speed.",
    accent: "from-indigo-500 to-blue-500",
  },
] as const;

const traceLines = [
  { type: "dim", text: "▶  planner          " },
  { type: "ok",  text: "✓  memory_recall     42ms" },
  { type: "ok",  text: "✓  pgvector_search   18ms" },
  { type: "active", text: "⟳  synthesizer     streaming…" },
];

export function HomeLanding() {
  return (
    <div className="relative flex min-h-screen flex-col overflow-x-hidden bg-flow-950">
      {/* ── WebGL backdrop ── */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[900px] overflow-hidden">
        <HeroCanvas className="h-full w-full" />
        {/* bloom orbs — bigger + brighter than before */}
        <div className="absolute left-1/2 top-[-12%] h-[640px] w-[1000px] -translate-x-1/2 rounded-full bg-flow-violet/30 blur-[160px]" />
        <div className="absolute left-[10%] top-[25%] h-[360px] w-[480px] rounded-full bg-fuchsia-600/18 blur-[120px]" />
        <div className="absolute right-[5%] top-[10%] h-[320px] w-[440px] rounded-full bg-indigo-500/15 blur-[100px]" />
        <div className="absolute right-[30%] top-[50%] h-[200px] w-[300px] rounded-full bg-violet-700/20 blur-[80px]" />
        <div className="scanlines absolute inset-0 opacity-[0.03]" />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-flow-950/30 to-flow-950" />
      </div>

      <div className="relative z-10 flex flex-1 flex-col">
        <PublicHeader />

        <main className="flex-1 pb-24">
          {/* ── HERO ── */}
          <section className="mx-auto grid max-w-[1240px] grid-cols-1 gap-10 px-4 pt-20 md:grid-cols-[1.15fr_0.85fr] lg:gap-16 lg:pt-28">

            {/* LEFT: copy */}
            <div className="flex flex-col justify-center">
              {/* live badge */}
              <div className="mb-6 inline-flex w-fit items-center gap-2 rounded-full border border-flow-violet/40 bg-flow-violet/12 px-4 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-flow-violet shadow-[0_0_20px_rgba(139,92,246,0.25)]">
                <span className="h-2 w-2 animate-pulse rounded-full bg-flow-violet shadow-[0_0_6px_#8b5cf6]" />
                Flow Workspace
              </div>

              {/* headline */}
              <h1 className="font-mono text-5xl font-bold leading-[1.05] tracking-[-0.03em] text-flow-50 lg:text-7xl">
                The cognitive<br />layer for your{" "}
                <span className="relative inline-block">
                  <span className="bg-gradient-to-r from-flow-violet via-fuchsia-400 to-pink-400 bg-clip-text text-transparent">
                    agents.
                  </span>
                  <span className="absolute -inset-x-2 inset-y-0 -z-10 blur-2xl bg-gradient-to-r from-flow-violet/30 via-fuchsia-500/20 to-transparent" />
                </span>
              </h1>

              <p className="mt-6 max-w-lg font-mono text-sm leading-[1.75] text-flow-400">
                Open-source, highly observable agent platform. Build with FastAPI,
                LangGraph, and Next.js. Long-term memory, continuous evaluation,
                and deterministic streaming.
              </p>

              <EnterAppCta />

              {/* stats */}
              <div className="mt-10 grid grid-cols-3 gap-3">
                {[
                  { val: "< 120ms", lbl: "TTFB Stream", glow: "shadow-[0_0_30px_rgba(139,92,246,0.2)]" },
                  { val: "O(1)", lbl: "Memory Recall", glow: "shadow-[0_0_30px_rgba(217,70,239,0.15)]" },
                  { val: "100%", lbl: "Type Safe", glow: "shadow-[0_0_30px_rgba(99,102,241,0.15)]" },
                ].map((stat) => (
                  <div
                    key={stat.lbl}
                    className={`relative overflow-hidden rounded-[8px] border border-flow-700/60 bg-gradient-to-br from-flow-900 to-flow-950 p-4 ${stat.glow}`}
                  >
                    <div className="absolute inset-0 bg-gradient-to-br from-flow-violet/5 to-transparent" />
                    <div className="relative font-mono text-2xl font-bold text-flow-50">{stat.val}</div>
                    <div className="relative mt-1 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-flow-500">
                      {stat.lbl}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* RIGHT: live trace panel */}
            <div className="relative flex flex-col gap-0 rounded-[10px] border border-flow-700/50 bg-gradient-to-br from-flow-900 via-flow-900 to-flow-950 shadow-[0_0_60px_rgba(139,92,246,0.15),inset_0_1px_0_rgba(255,255,255,0.05)]">
              {/* top chrome bar */}
              <div className="flex items-center justify-between border-b border-flow-800 px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1.5">
                    <div className="h-2.5 w-2.5 rounded-full bg-red-500/70" />
                    <div className="h-2.5 w-2.5 rounded-full bg-yellow-500/70" />
                    <div className="h-2.5 w-2.5 rounded-full bg-green-500/70" />
                  </div>
                  <span className="ml-2 font-mono text-[10px] text-flow-600">deer-flow / trace</span>
                </div>
                <div className="flex items-center gap-2 rounded-full border border-flow-violet/40 bg-flow-violet/10 px-3 py-1">
                  <div className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399]" />
                  <span className="font-mono text-[10px] font-semibold text-emerald-400">Execution active</span>
                </div>
              </div>

              {/* trace body */}
              <div className="flex flex-1 flex-col gap-2 p-4">
                {/* pipeline steps */}
                <div className="rounded-[6px] border border-flow-800 bg-flow-950/80 p-3">
                  <div className="mb-2.5 font-mono text-[9px] font-semibold uppercase tracking-[0.15em] text-flow-600">
                    <Terminal className="mb-0.5 mr-1 inline h-3 w-3" />Pipeline Trace
                  </div>
                  <div className="space-y-1.5">
                    {traceLines.map((line, i) => (
                      <div key={i} className="flex items-center justify-between font-mono text-[11px]">
                        <span className={
                          line.type === "ok" ? "text-emerald-400" :
                          line.type === "active" ? "text-flow-violet" :
                          "text-flow-700"
                        }>
                          {line.text}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* metrics row */}
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { lbl: "Routing", val: "Semantic Match", color: "text-flow-violet" },
                    { lbl: "Tool Calls", val: "pgvector_search", color: "text-emerald-400" },
                  ].map((item) => (
                    <div key={item.lbl} className="rounded-[6px] border border-flow-800 bg-flow-950/60 p-3">
                      <div className="font-mono text-[9px] uppercase tracking-[0.12em] text-flow-600">{item.lbl}</div>
                      <div className={`mt-1.5 font-mono text-xs font-semibold ${item.color}`}>{item.val}</div>
                    </div>
                  ))}
                </div>

                {/* streaming code block */}
                <div className="rounded-[6px] border border-flow-violet/20 bg-flow-950/80 p-3 shadow-[inset_0_0_20px_rgba(139,92,246,0.06)]">
                  <div className="mb-2 font-mono text-[9px] font-semibold uppercase tracking-[0.12em] text-flow-violet/70">
                    Streaming Output
                  </div>
                  <pre className="font-mono text-[11px] leading-[1.8] text-flow-300">
<code><span className="text-flow-600">import</span>{" "}<span className="text-flow-200">{"{ Memory }"}</span>{" "}<span className="text-flow-600">from</span>{" "}<span className="text-fuchsia-400">&quot;flow-core&quot;</span>{";"}
<span className="text-flow-600">{"// "}</span><span className="text-flow-600">Autonomous context resolution</span>
<span className="text-flow-600">await</span>{" "}<span className="text-emerald-400">agent</span><span className="text-flow-500">.</span><span className="text-flow-violet">reflect</span><span className="text-flow-400">(state)</span>{";"}
<span className="text-flow-600 animate-pulse">█</span></code>
                  </pre>
                </div>
              </div>
            </div>
          </section>

          {/* ── FEATURE GRID ── */}
          <section className="mx-auto mt-16 max-w-[1240px] px-4">
            <div className="mb-8 text-center">
              <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-flow-violet">
                Platform capabilities
              </p>
              <h2 className="mt-2 font-mono text-2xl font-bold tracking-tight text-flow-50 lg:text-3xl">
                Built for production agentic systems
              </h2>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {pillars.map(({ icon: Icon, label, text, accent }) => (
                <div
                  key={label}
                  className="group relative overflow-hidden rounded-[10px] border border-flow-800 bg-gradient-to-br from-flow-900 to-flow-950 p-6 transition-all duration-300 hover:border-flow-700 hover:shadow-[0_0_40px_rgba(139,92,246,0.12)]"
                >
                  {/* gradient top line */}
                  <div className={`absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r ${accent} opacity-60 group-hover:opacity-100 transition-opacity`} />
                  {/* icon */}
                  <div className={`mb-4 inline-flex h-10 w-10 items-center justify-center rounded-[8px] bg-gradient-to-br ${accent} bg-opacity-10 p-0.5`}>
                    <div className="flex h-full w-full items-center justify-center rounded-[7px] bg-flow-950">
                      <Icon className="h-5 w-5 text-flow-200" />
                    </div>
                  </div>
                  <h3 className="mb-2 font-mono text-sm font-bold tracking-tight text-flow-50">{label}</h3>
                  <p className="font-mono text-xs leading-[1.8] text-flow-500">{text}</p>
                </div>
              ))}
            </div>
          </section>
        </main>

        <footer className="border-t border-flow-800/60 bg-flow-950 py-8 text-center">
          <div className="mb-2 flex items-center justify-center gap-2">
            <FlowMark size={20} className="text-flow-600" />
            <span className="font-mono text-xs font-semibold text-flow-500">Flow Platform</span>
          </div>
          <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-flow-700">
            Agent Workspace · FastAPI · LangGraph · Next.js · pgvector
          </p>
        </footer>
      </div>
    </div>
  );
}
