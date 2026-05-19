"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Brain,
  Check,
  Code2,
  Loader2,
  Newspaper,
  Search,
  Sparkles,
  Zap,
} from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";
import { ApiError, apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Me = { workspaces: { id: string; name: string }[] };

interface AgentConfig {
  name: string;
  template: "linear-3" | "tool-agent";
  system_prompt: string;
  tools: {
    retrieve: boolean;
    sandbox: boolean;
    long_term_memory: boolean;
    tavily_search: boolean;
    fetch_webpage: boolean;
    arxiv_search: boolean;
    hf_papers: boolean;
  };
}

const TEMPLATES: {
  id: string;
  label: string;
  description: string;
  icon: React.ElementType;
  accentClass: string;
  config: AgentConfig;
}[] = [
  {
    id: "second-brain",
    label: "Second Brain",
    description: "Answers questions using your uploaded documents, PDFs, and web pages.",
    icon: BookOpen,
    accentClass: "border-blue-500/40 bg-blue-500/5 hover:bg-blue-500/10",
    config: {
      name: "Second Brain",
      template: "linear-3",
      system_prompt:
        "You are a knowledgeable assistant with access to the user's personal knowledge base. Answer questions thoroughly using the retrieved documents. Always cite sources when available.",
      tools: { retrieve: true, sandbox: false, long_term_memory: true, tavily_search: false, fetch_webpage: false, arxiv_search: false, hf_papers: false },
    },
  },
  {
    id: "web-researcher",
    label: "Web Researcher",
    description: "Searches the web and fetches pages to answer questions with live data.",
    icon: Search,
    accentClass: "border-green-500/40 bg-green-500/5 hover:bg-green-500/10",
    config: {
      name: "Web Researcher",
      template: "tool-agent",
      system_prompt:
        "You are a web research agent. Use Tavily search and page fetching to find accurate, up-to-date information. Synthesize multiple sources and cite URLs in your answers.",
      tools: { retrieve: false, sandbox: false, long_term_memory: false, tavily_search: true, fetch_webpage: true, arxiv_search: false, hf_papers: false },
    },
  },
  {
    id: "paper-synthesizer",
    label: "Paper Synthesizer",
    description: "Fetches HuggingFace daily papers and ArXiv research. Synthesizes key insights.",
    icon: Newspaper,
    accentClass: "border-orange-500/40 bg-orange-500/5 hover:bg-orange-500/10",
    config: {
      name: "Paper Synthesizer",
      template: "tool-agent",
      system_prompt:
        "You are an AI research digest agent. Fetch today's HuggingFace papers and search ArXiv for relevant academic work. Produce clear, structured summaries with key contributions, methods, and implications. Group papers by theme when relevant.",
      tools: { retrieve: false, sandbox: false, long_term_memory: false, tavily_search: false, fetch_webpage: true, arxiv_search: true, hf_papers: true },
    },
  },
  {
    id: "code-runner",
    label: "Code Runner",
    description: "Writes and executes Python code in a sandbox to solve problems and analyze data.",
    icon: Code2,
    accentClass: "border-amber-500/40 bg-amber-500/5 hover:bg-amber-500/10",
    config: {
      name: "Code Runner",
      template: "linear-3",
      system_prompt:
        "You are a Python coding assistant. When solving problems, write clean Python code and execute it to verify results. Show your work step by step. Handle errors gracefully.",
      tools: { retrieve: false, sandbox: true, long_term_memory: false, tavily_search: false, fetch_webpage: false, arxiv_search: false, hf_papers: false },
    },
  },
];

const TOOL_LABELS: { key: keyof AgentConfig["tools"]; label: string; description: string; badge?: string }[] = [
  { key: "retrieve", label: "Knowledge search", description: "Semantic search over workspace documents" },
  { key: "sandbox", label: "Python sandbox", description: "Execute code in an isolated runner" },
  { key: "long_term_memory", label: "Long-term memory", description: "Recall past conversations" },
  { key: "tavily_search", label: "Tavily web search", description: "Search the live web", badge: "API key required" },
  { key: "fetch_webpage", label: "Fetch webpage", description: "Read any URL content" },
  { key: "arxiv_search", label: "ArXiv search", description: "Search academic papers" },
  { key: "hf_papers", label: "HF Daily Papers", description: "HuggingFace trending AI research" },
];

export default function NewAgentPage() {
  const router = useRouter();
  const routerRef = useRef(router);
  const [wsId, setWsId] = useState<string | null>(null);
  const [step, setStep] = useState<1 | 2 | 3>(1);

  const [vibeText, setVibeText] = useState("");
  const [vibing, setVibing] = useState(false);
  const [vibeErr, setVibeErr] = useState<string | null>(null);
  const [pickedTemplate, setPickedTemplate] = useState<string | null>(null);

  const [config, setConfig] = useState<AgentConfig>({
    name: "",
    template: "linear-3",
    system_prompt: "",
    tools: { retrieve: true, sandbox: false, long_term_memory: false, tavily_search: false, fetch_webpage: false, arxiv_search: false, hf_papers: false },
  });

  const [creating, setCreating] = useState(false);
  const [createErr, setCreateErr] = useState<string | null>(null);

  useEffect(() => {
    routerRef.current = router;
  }, [router]);

  useEffect(() => {
    if (!getToken()) { routerRef.current.replace("/login"); return; }
    apiFetch<Me>("/api/v1/auth/me")
      .then((m) => { if (m.workspaces[0]) setWsId(m.workspaces[0].id); })
      .catch(() => {});
  }, []);

  function applyTemplate(tpl: (typeof TEMPLATES)[number]) {
    setPickedTemplate(tpl.id);
    setConfig({ ...tpl.config });
  }

  async function runVibe() {
    if (!wsId || !vibeText.trim()) return;
    setVibing(true);
    setVibeErr(null);
    try {
      const result = await apiFetch<AgentConfig>(`/api/v1/workspaces/${wsId}/agents/vibe`, {
        method: "POST",
        json: { description: vibeText },
      });
      setConfig({
        name: result.name ?? "",
        template: result.template ?? "linear-3",
        system_prompt: result.system_prompt ?? "",
        tools: { ...config.tools, ...(result.tools ?? {}) },
      });
      setPickedTemplate("vibe");
      setStep(2);
    } catch (e) {
      setVibeErr(e instanceof ApiError ? `${e.status}: ${e.body}` : "Vibe generation failed.");
    } finally {
      setVibing(false);
    }
  }

  async function createAgent() {
    if (!wsId) return;
    setCreating(true);
    setCreateErr(null);
    try {
      const result = await apiFetch<{ id: string }>("/api/v1/agents", {
        method: "POST",
        json: {
          workspace_id: wsId,
          name: config.name || "New Agent",
          template: config.template,
          config: {
            graph: { template: config.template },
            system_prompt: config.system_prompt,
            tools: config.tools,
          },
        },
      });
      void result;
      routerRef.current.push("/run");
    } catch (e) {
      setCreateErr(e instanceof ApiError ? `${e.status}: ${e.body}` : "Failed to create agent.");
      setCreating(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl space-y-8 pb-10">
      <FlowPageHeader
        eyebrow={
          <Badge variant="outline" className="gap-1 font-mono text-[10px] uppercase tracking-wide">
            <Zap className="h-3 w-3" aria-hidden />
            New Agent
          </Badge>
        }
        title="Build your agent"
        description="Pick a template or describe what you want — the AI will configure it for you."
        actions={
          <Button variant="outline" size="sm" onClick={() => router.push("/agents")}>
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
            Back
          </Button>
        }
      />

      {/* Step indicator */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {(["Choose", "Configure", "Create"] as const).map((label, i) => {
          const n = (i + 1) as 1 | 2 | 3;
          const active = step === n;
          const done = step > n;
          return (
            <div key={label} className="flex items-center gap-2">
              <span
                className={cn(
                  "flex h-5 w-5 items-center justify-center rounded-full border text-[10px] font-semibold",
                  active ? "border-flow-violet bg-flow-violet/20 text-foreground" : done ? "border-flow-done bg-flow-done/20 text-foreground" : "border-border text-muted-foreground",
                )}
              >
                {done ? <Check className="h-2.5 w-2.5" /> : n}
              </span>
              <span className={cn(active ? "font-medium text-foreground" : "")}>{label}</span>
              {i < 2 && <ArrowRight className="h-3 w-3 opacity-40" />}
            </div>
          );
        })}
      </div>

      {/* Step 1 — Choose */}
      {step === 1 && (
        <div className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-2">
            {TEMPLATES.map((tpl) => {
              const Icon = tpl.icon;
              const picked = pickedTemplate === tpl.id;
              return (
                <button
                  key={tpl.id}
                  type="button"
                  onClick={() => applyTemplate(tpl)}
                  className={cn(
                    "group relative flex flex-col gap-2 rounded-xl border p-4 text-left transition-all",
                    picked ? "border-flow-violet/60 bg-flow-violet/10 ring-1 ring-flow-violet/30" : tpl.accentClass,
                  )}
                >
                  {picked && (
                    <span className="absolute right-3 top-3 flex h-4 w-4 items-center justify-center rounded-full bg-flow-violet">
                      <Check className="h-2.5 w-2.5 text-white" />
                    </span>
                  )}
                  <Icon className="h-5 w-5 text-foreground/80" aria-hidden />
                  <span className="text-sm font-semibold text-foreground">{tpl.label}</span>
                  <span className="text-[12px] text-muted-foreground leading-relaxed">{tpl.description}</span>
                  <Badge variant="outline" className="mt-1 w-fit font-mono text-[10px]">
                    {tpl.config.template}
                  </Badge>
                </button>
              );
            })}
          </div>

          {/* Vibe input */}
          <Card className="border-flow-800">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-flow-violet" aria-hidden />
                <CardTitle className="text-base">Vibe code your agent</CardTitle>
              </div>
              <CardDescription className="text-[13px]">
                Describe what you want — the AI generates name, system prompt, and tool selection.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Textarea
                value={vibeText}
                onChange={(e) => setVibeText(e.target.value)}
                placeholder="e.g. An agent that fetches HuggingFace papers every morning and writes a digest with key takeaways grouped by topic"
                rows={3}
                className="resize-none text-sm"
              />
              {vibeErr && (
                <Alert variant="destructive" className="py-2">
                  <AlertCircle className="h-3.5 w-3.5" />
                  <AlertDescription className="text-xs">{vibeErr}</AlertDescription>
                </Alert>
              )}
              <Button onClick={() => void runVibe()} disabled={vibing || !vibeText.trim() || !wsId} size="sm">
                {vibing ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <Sparkles className="mr-2 h-3.5 w-3.5" />}
                Generate config
              </Button>
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button onClick={() => setStep(2)} disabled={!pickedTemplate && !config.name}>
              Configure
              <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}

      {/* Step 2 — Configure */}
      {step === 2 && (
        <div className="space-y-6">
          <Card className="border-flow-800">
            <CardHeader>
              <CardTitle className="text-base">Agent identity</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="agent-name">Name</Label>
                <Input
                  id="agent-name"
                  value={config.name}
                  onChange={(e) => setConfig((c) => ({ ...c, name: e.target.value }))}
                  placeholder="My Research Agent"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="system-prompt">System prompt</Label>
                <Textarea
                  id="system-prompt"
                  value={config.system_prompt}
                  onChange={(e) => setConfig((c) => ({ ...c, system_prompt: e.target.value }))}
                  rows={5}
                  placeholder="Instructions for the agent…"
                  className="resize-y text-sm"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-muted-foreground text-xs">Template</Label>
                <div className="flex gap-2">
                  {(["linear-3", "tool-agent"] as const).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setConfig((c) => ({ ...c, template: t }))}
                      className={cn(
                        "rounded-lg border px-3 py-1.5 font-mono text-[11px] transition-colors",
                        config.template === t
                          ? "border-flow-violet/50 bg-flow-violet/10 text-foreground"
                          : "border-flow-800 text-muted-foreground hover:bg-muted/40",
                      )}
                    >
                      {t}
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-muted-foreground">
                  <code className="font-mono">linear-3</code>: planner → worker → synthesizer (best for RAG).{" "}
                  <code className="font-mono">tool-agent</code>: ReAct loop with function calling (best for web tools).
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-flow-800">
            <CardHeader>
              <CardTitle className="text-base">Tools</CardTitle>
              <CardDescription className="text-[13px]">Enable the capabilities your agent needs.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {TOOL_LABELS.map(({ key, label, description, badge }) => (
                <div key={key} className="flex items-center justify-between gap-4 rounded-lg border border-flow-800 px-3 py-2.5">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-foreground">{label}</span>
                      {badge && (
                        <Badge variant="outline" className="h-4 rounded px-1 py-0 text-[9px] text-muted-foreground">
                          {badge}
                        </Badge>
                      )}
                    </div>
                    <p className="text-[12px] text-muted-foreground">{description}</p>
                  </div>
                  <Switch
                    checked={config.tools[key]}
                    onCheckedChange={(v) =>
                      setConfig((c) => ({ ...c, tools: { ...c.tools, [key]: v } }))
                    }
                  />
                </div>
              ))}
            </CardContent>
          </Card>

          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep(1)}>
              <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
              Back
            </Button>
            <Button onClick={() => setStep(3)}>
              Review
              <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}

      {/* Step 3 — Create */}
      {step === 3 && (
        <div className="space-y-6">
          <Card className="border-flow-800">
            <CardHeader>
              <CardTitle className="text-base">Review & create</CardTitle>
              <CardDescription className="text-[13px]">Confirm the configuration before creating your agent.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1">
                <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Name</p>
                <p className="text-sm font-medium">{config.name || "(unnamed)"}</p>
              </div>
              <div className="space-y-1">
                <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Template</p>
                <Badge variant="outline" className="font-mono text-xs">{config.template}</Badge>
              </div>
              <div className="space-y-1">
                <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">System prompt</p>
                <p className="rounded-lg bg-muted/30 px-3 py-2 text-[13px] leading-relaxed text-foreground/80">
                  {config.system_prompt || "(none)"}
                </p>
              </div>
              <div className="space-y-1.5">
                <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Enabled tools</p>
                <div className="flex flex-wrap gap-1.5">
                  {TOOL_LABELS.filter((t) => config.tools[t.key]).map((t) => (
                    <Badge key={t.key} variant="secondary" className="text-[11px]">
                      {t.label}
                    </Badge>
                  ))}
                  {TOOL_LABELS.every((t) => !config.tools[t.key]) && (
                    <span className="text-[12px] text-muted-foreground">No tools enabled</span>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {createErr && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{createErr}</AlertDescription>
            </Alert>
          )}

          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep(2)}>
              <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
              Edit
            </Button>
            <Button onClick={() => void createAgent()} disabled={creating}>
              {creating ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Brain className="mr-2 h-4 w-4" />
              )}
              Create agent
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
