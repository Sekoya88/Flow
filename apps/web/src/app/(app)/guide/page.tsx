import {
  Brain,
  CalendarClock,
  CheckCircle,
  History,
  HelpCircle,
  LayoutDashboard,
  MessageSquare,
  Network,
  Newspaper,
  ScrollText,
  Sparkles,
  Terminal,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";

type GuideSection = {
  id: string;
  icon: LucideIcon;
  title: string;
  what: string;
  action: string;
};

const sections: GuideSection[] = [
  {
    id: "dashboard",
    icon: LayoutDashboard,
    title: "Dashboard",
    what: "Workspace overview — agent count, execution volume, pending proposals, and recent activity at a glance.",
    action: "Check here first when you come back to a workspace to see what changed.",
  },
  {
    id: "run",
    icon: MessageSquare,
    title: "Run",
    what: "Where you chat with an agent. Streams tokens live over SSE, shows tool calls and retrieved knowledge inline.",
    action: "Pick an agent, type a message, watch the trace expand as it plans, retrieves, and answers.",
  },
  {
    id: "skills",
    icon: Sparkles,
    title: "Skills",
    what: "Reusable instructions an agent can match on user intent — markdown procedures with trigger phrases.",
    action: "Write a skill once for a repeated task; the agent's reflector can also auto-propose new ones after a high-grade run.",
  },
  {
    id: "knowledge",
    icon: ScrollText,
    title: "Knowledge",
    what: "Your retrieval corpus — upload files, paste text, or crawl a URL. Everything gets chunked and embedded.",
    action: "Open a source's chunk drawer and use \"Use in agent memory\" to promote a high-value chunk into an agent's long-term memory.",
  },
  {
    id: "memory",
    icon: Brain,
    title: "Memory",
    what: "Inspect what an agent has learned: episodic (per-run summaries), semantic (facts), and typed user preferences.",
    action: "Use this to debug why an agent recalled (or failed to recall) something from a past session.",
  },
  {
    id: "agents",
    icon: Workflow,
    title: "Agents",
    what: "Create and configure agents — model, tools, graph template (linear-3, tool-agent, researcher-critic-writer, etc).",
    action: "Start from a template close to your use case, then tune tools and the system prompt.",
  },
  {
    id: "graph",
    icon: Network,
    title: "Graph",
    what: "The workspace knowledge graph — entities and relations extracted from executions and documents, ranked by PageRank.",
    action: "Explore it to find which topics/entities are most central to your workspace's accumulated knowledge.",
  },
  {
    id: "proposals",
    icon: Sparkles,
    title: "Proposals",
    what: "Structural changes an agent's reflector proposed after a low or high grade run — new skills, genome mutations, regression flags.",
    action: "Review and approve/reject; approving a genome candidate promotes it to the agent's active version.",
  },
  {
    id: "schedules",
    icon: CalendarClock,
    title: "Schedules",
    what: "Cron-driven runs — have an agent execute a prompt template on a recurring schedule, optionally with a webhook delivery.",
    action: "Use for recurring reports or monitoring tasks you don't want to trigger by hand.",
  },
  {
    id: "evals",
    icon: CheckCircle,
    title: "Evals",
    what: "Golden-set benchmarks — LLM-as-judge pipeline that re-runs fixed test cases against an agent to catch regressions.",
    action: "Add a golden case after fixing a bug so a future change can't silently reintroduce it.",
  },
  {
    id: "executions",
    icon: History,
    title: "Executions",
    what: "Full history of past runs across all agents, with status, duration, and the resulting answer.",
    action: "Use to audit or replay what an agent actually did for a given request.",
  },
  {
    id: "logs",
    icon: Terminal,
    title: "Logs",
    what: "Raw structured logs and tool-call traces for debugging an execution at the node level.",
    action: "Drop here when an execution behaved unexpectedly and you need to see exactly what each graph node returned.",
  },
  {
    id: "research",
    icon: Newspaper,
    title: "Research",
    what: "Output feed for agents built on the researcher-critic-writer template — multi-iteration research reports.",
    action: "Check here for the final write-up after a research-style agent finishes its critique loop.",
  },
];

export default function GuidePage() {
  return (
    <div className="mx-auto w-full max-w-4xl space-y-8 pb-8">
      <FlowPageHeader
        leading={<HelpCircle className="h-5 w-5" />}
        eyebrow={
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-flow-violet/80">
            Guide
          </span>
        }
        title="Finding your way around Flow"
        description="One section per area of the app — what it's for and the one action worth knowing. Just finished the setup wizard? This is the standing reference for everything after it."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {sections.map(({ id, icon: Icon, title, what, action }) => (
          <div
            key={id}
            id={id}
            className="rounded-xl border border-flow-800 bg-card/40 p-5 transition-colors hover:border-flow-violet/40"
          >
            <div className="mb-3 flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-flow-800 bg-flow-violet/10 text-flow-violet">
                <Icon className="h-4 w-4" aria-hidden />
              </div>
              <h2 className="font-mono text-sm font-semibold text-foreground">{title}</h2>
            </div>
            <p className="text-sm leading-relaxed text-muted-foreground">{what}</p>
            <p className="mt-2 text-xs leading-relaxed text-flow-violet/90">{action}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
