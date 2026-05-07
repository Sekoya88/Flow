"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, Loader2, MessageSquare, Plus, Workflow } from "lucide-react";
import { AgentTopologyCanvas, type CatalogEdge, type CatalogNode } from "@/components/agents/AgentTopologyCanvas";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiError, apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { FlowPageHeader } from "@/components/layout/FlowPageHeader";

type Me = { workspaces: { id: string; name: string }[] };

type AgentRow = {
  id: string;
  name: string;
  template: string;
  config: Record<string, unknown>;
};

type DeerCatalog = {
  id: string;
  title: string;
  nodes: CatalogNode[];
  edges: CatalogEdge[];
};

type GraphCatalog = {
  deer_flow_templates: DeerCatalog[];
  agentic_rag: {
    id: string;
    title: string;
    description?: string;
    nodes: CatalogNode[];
    edges: CatalogEdge[];
  };
};

function templateFromAgent(a: AgentRow | undefined): string {
  if (!a?.config) return "linear-3";
  const g = a.config.graph;
  if (g && typeof g === "object" && !Array.isArray(g) && typeof (g as { template?: unknown }).template === "string") {
    return (g as { template: string }).template;
  }
  if (typeof a.config.template === "string") return a.config.template;
  return "linear-3";
}

export default function AgentsGraphPage() {
  const router = useRouter();
  const routerRef = useRef(router);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<GraphCatalog | null>(null);
  const [agents, setAgents] = useState<AgentRow[]>([]);
  const [agentId, setAgentId] = useState<string | null>(null);
  const [deerPick, setDeerPick] = useState<string>("linear-3");
  const [layer, setLayer] = useState<"deer" | "agentic_rag">("deer");

  useEffect(() => {
    routerRef.current = router;
  }, [router]);

  useEffect(() => {
    if (!getToken()) {
      routerRef.current.replace("/login");
      return;
    }
    setLoading(true);
    setErr(null);
    Promise.all([
      apiFetch<GraphCatalog>("/api/v1/meta/graph-catalog"),
      apiFetch<Me>("/api/v1/auth/me"),
    ])
      .then(([cat, me]) => {
        setCatalog(cat);
        const w = me.workspaces[0];
        if (!w) {
          setErr("No workspace for this account.");
          return;
        }
        return apiFetch<{ agents: AgentRow[] }>(`/api/v1/workspaces/${w.id}/agents`);
      })
      .then((a) => {
        if (!a?.agents?.length) return;
        setAgents(a.agents);
        const first = a.agents[0];
        setAgentId(first.id);
        setDeerPick(templateFromAgent(first));
      })
      .catch((e) => {
        setErr(e instanceof ApiError ? `${e.status}: ${e.body}` : "Could not load graph catalog.");
      })
      .finally(() => setLoading(false));
  }, []);

  const activeAgent = useMemo(() => agents.find((x) => x.id === agentId), [agents, agentId]);

  useEffect(() => {
    if (activeAgent) setDeerPick(templateFromAgent(activeAgent));
  }, [activeAgent]);

  const deerGraph = useMemo(() => {
    if (!catalog) return null;
    return catalog.deer_flow_templates.find((t) => t.id === deerPick) ?? catalog.deer_flow_templates[0] ?? null;
  }, [catalog, deerPick]);

  const agentic = catalog?.agentic_rag;

  if (loading || !catalog) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground text-sm">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        Loading topology…
      </div>
    );
  }

  if (err) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Unable to load agents graph</AlertTitle>
        <AlertDescription>{err}</AlertDescription>
      </Alert>
    );
  }

  const canvasNodes = layer === "deer" && deerGraph ? deerGraph.nodes : agentic?.nodes ?? [];
  const canvasEdges = layer === "deer" && deerGraph ? deerGraph.edges : agentic?.edges ?? [];
  const canvasId = layer === "deer" ? deerGraph?.id ?? "deer" : "agentic_rag";

  return (
    <div className="mx-auto w-full max-w-6xl space-y-8 pb-10">
      <FlowPageHeader
        eyebrow={
          <Badge variant="outline" className="gap-1 font-mono text-[10px] uppercase tracking-wide">
            <Workflow className="h-3 w-3" aria-hidden />
            Topology
          </Badge>
        }
        title="Agent graphs"
        description="Explore the LangGraph templates your workspace agents use and the agentic RAG retrieval subgraph (Qdrant + supervisor loop). Pan and zoom the canvas — Obsidian-style linked nodes."
      />

      <Card className="border-border/80 shadow-sm">
        <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-1">
            <CardTitle className="text-lg">Graph layer</CardTitle>
            <CardDescription className="text-[13px]">
              <strong>Deer flow</strong> is the main agent pipeline (planner → worker → synthesizer or other templates).{" "}
              <strong>Agentic RAG</strong> runs inside retrieval when enabled in settings.
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setLayer("deer")}
              className={cn(
                "rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                layer === "deer"
                  ? "border-flow-brand/50 bg-flow-brand/10 text-foreground"
                  : "border-border/60 text-muted-foreground hover:bg-muted/50",
              )}
            >
              Deer flow template
            </button>
            <button
              type="button"
              onClick={() => setLayer("agentic_rag")}
              className={cn(
                "rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                layer === "agentic_rag"
                  ? "border-flow-thinking/50 bg-flow-thinking/10 text-foreground"
                  : "border-border/60 text-muted-foreground hover:bg-muted/50",
              )}
            >
              Agentic RAG subgraph
            </button>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {layer === "deer" ? (
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
              <div className="space-y-2 sm:min-w-[220px]">
                <span className="text-xs font-medium text-muted-foreground">Workspace agent</span>
                <Select
                  value={agentId ?? undefined}
                  onValueChange={(v) => {
                    if (v != null) setAgentId(v);
                  }}
                >
                  <SelectTrigger className="w-full sm:w-[280px]">
                    <SelectValue placeholder="Agent" />
                  </SelectTrigger>
                  <SelectContent>
                    {agents.map((a) => (
                      <SelectItem key={a.id} value={a.id}>
                        {a.name || a.template}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-[11px] text-muted-foreground">
                  Config template:{" "}
                  <code className="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">{deerPick}</code>
                </p>
              </div>
              <div className="space-y-2 sm:flex-1">
                <span className="text-xs font-medium text-muted-foreground">Topology preview</span>
                <Select
                  value={deerPick}
                  onValueChange={(v) => {
                    if (v != null) setDeerPick(v);
                  }}
                >
                  <SelectTrigger className="w-full sm:max-w-md">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {catalog.deer_flow_templates.map((t) => (
                      <SelectItem key={t.id} value={t.id}>
                        {t.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground leading-relaxed">{agentic?.description}</p>
          )}

          <AgentTopologyCanvas graphId={canvasId} nodes={canvasNodes} edges={canvasEdges} />

          <div className="flex flex-wrap gap-2 border-t border-border/40 pt-4">
            <Link
              href="/run"
              className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 px-3 py-1.5 text-xs font-medium hover:bg-muted/50"
            >
              <MessageSquare className="h-3.5 w-3.5" aria-hidden />
              Run agent
            </Link>
            <Link
              href="/agents/new"
              className="inline-flex items-center gap-1.5 rounded-lg border border-flow-brand/40 bg-flow-brand/10 px-3 py-1.5 text-xs font-medium hover:bg-flow-brand/20"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden />
              New agent
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
