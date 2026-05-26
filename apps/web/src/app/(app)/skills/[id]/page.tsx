"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Background,
  Controls,
  type Edge,
  type Node,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  AlertCircle,
  ArrowLeft,
  GitBranch,
  Loader2,
  Sparkles,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/api";
import { useWorkspaceId } from "@/lib/useWorkspace";
import { cn } from "@/lib/utils";

type SkillFull = {
  id: string;
  name: string;
  description: string;
  category: string;
  triggers: string[];
  allowed_tools: string[];
  content_md: string;
  score: number;
  use_count: number;
  active: boolean;
};

type SkillCatalogRow = { id: string; name: string; category: string; description: string };

// ── Parse [[skill-name]] wiki-links from skill body ──────────────────────────

function parseWikiLinks(content: string): string[] {
  const matches = content.matchAll(/\[\[([^\]]+)\]\]/g);
  return [...matches].map((m) => m[1].trim().toLowerCase());
}

// ── Color by category ────────────────────────────────────────────────────────

const CAT_COLORS: Record<string, string> = {
  Research: "#0ea5e9",
  Code: "#10b981",
  Communication: "#f59e0b",
  Analysis: "#8b5cf6",
  Memory: "#f43f5e",
  Planning: "#f97316",
  General: "#64748b",
};

function catColor(cat: string): string {
  return CAT_COLORS[cat] ?? "#64748b";
}

// ── Layout (simple layered left→right) ──────────────────────────────────────

function buildGraph(
  focal: SkillFull,
  allSkills: SkillCatalogRow[],
): { nodes: Node[]; edges: Edge[] } {
  const linked = parseWikiLinks(focal.content_md);
  const linkedSkills = allSkills.filter((s) => linked.includes(s.name.toLowerCase()));
  const referencedBy = allSkills.filter((s) => {
    // We don't have content_md for all skills — skip reverse edges
    return false;
  });

  const nodeList: Node[] = [];
  const edgeList: Edge[] = [];

  // Focal node
  const focalColor = catColor(focal.category);
  nodeList.push({
    id: focal.id,
    position: { x: 400, y: 200 },
    data: {
      label: (
        <div className="flex flex-col items-center gap-0.5">
          <span className="font-mono text-[11px] font-bold">{focal.name}</span>
          <span className="font-mono text-[9px] opacity-60">{focal.category}</span>
        </div>
      ),
    },
    style: {
      width: 160,
      height: 60,
      borderRadius: 10,
      border: `2.5px solid ${focalColor}`,
      background: `${focalColor}22`,
      color: "#f1f5f9",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      boxShadow: `0 0 0 3px ${focalColor}44`,
    },
  });

  // Dependencies (outbound)
  linkedSkills.forEach((s, i) => {
    const color = catColor(s.category);
    const y = (i - (linkedSkills.length - 1) / 2) * 90 + 200;
    nodeList.push({
      id: s.id,
      position: { x: 700, y },
      data: {
        label: (
          <div className="flex flex-col items-center gap-0.5">
            <span className="font-mono text-[11px] font-semibold">{s.name}</span>
            <span className="font-mono text-[9px] opacity-60">{s.category}</span>
          </div>
        ),
      },
      style: {
        width: 150,
        height: 56,
        borderRadius: 8,
        border: `1.5px solid ${color}`,
        background: `${color}18`,
        color: "#f1f5f9",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      },
    });
    edgeList.push({
      id: `${focal.id}->${s.id}`,
      source: focal.id,
      target: s.id,
      animated: false,
      label: "uses",
      labelStyle: { fontFamily: "monospace", fontSize: 9, fill: "#64748b" },
      style: { stroke: focalColor, strokeWidth: 1.5, opacity: 0.7 },
      markerEnd: { type: "arrowclosed" as const, color: focalColor },
    });
  });

  return { nodes: nodeList, edges: edgeList };
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function SkillChainPage() {
  const { id } = useParams<{ id: string }>();
  const { workspaceId } = useWorkspaceId();

  const [skill, setSkill] = useState<SkillFull | null>(null);
  const [allSkills, setAllSkills] = useState<SkillCatalogRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id || !workspaceId) return;
    setLoading(true);
    Promise.all([
      apiFetch<SkillFull>(`/api/v1/skills/${id}`),
      apiFetch<{ skills: SkillCatalogRow[] }>(
        `/api/v1/skills/catalog?workspace_id=${workspaceId}`,
      ),
    ])
      .then(([s, catalog]) => {
        setSkill(s);
        setAllSkills(catalog.skills ?? []);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [id, workspaceId]);

  const { nodes: initNodes, edges: initEdges } = useMemo(
    () =>
      skill && allSkills.length > 0
        ? buildGraph(skill, allSkills)
        : { nodes: [], edges: [] },
    [skill, allSkills],
  );

  const [rfNodes, setRfNodes, onNodesChange] = useNodesState<Node>([]);
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => { setRfNodes(initNodes); }, [initNodes, setRfNodes]);
  useEffect(() => { setRfEdges(initEdges); }, [initEdges, setRfEdges]);

  const linkedCount = useMemo(() => {
    if (!skill) return 0;
    return parseWikiLinks(skill.content_md).length;
  }, [skill]);

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-flow-500" />
      </div>
    );
  }

  if (error || !skill) {
    return (
      <div className="flex h-[60vh] flex-col items-center justify-center gap-3">
        <AlertCircle className="h-6 w-6 text-destructive" />
        <p className="font-mono text-xs text-flow-500">{error ?? "Skill not found"}</p>
        <Link href="/skills" className="font-mono text-[11px] text-flow-violet hover:underline">
          ← Back to Skills
        </Link>
      </div>
    );
  }

  const color = catColor(skill.category);

  return (
    <div className="flex h-full flex-col gap-4 p-4 animate-fade-in">
      {/* Back */}
      <Link
        href="/skills"
        className="inline-flex w-fit items-center gap-1.5 font-mono text-[11px] text-flow-500 hover:text-flow-200 transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Skills
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="font-mono text-sm font-bold text-flow-50">{skill.name}</h2>
            <Badge
              variant="outline"
              style={{ borderColor: `${color}50`, color }}
              className="font-mono text-[9px]"
            >
              {skill.category}
            </Badge>
            {!skill.active && (
              <Badge variant="outline" className="border-flow-700 font-mono text-[9px] text-flow-600">
                inactive
              </Badge>
            )}
          </div>
          {skill.description && (
            <p className="font-mono text-[11px] text-flow-500 max-w-lg">{skill.description}</p>
          )}
        </div>
        <div className="shrink-0 flex items-center gap-3 font-mono text-[10px] text-flow-600">
          <span className="flex items-center gap-1">
            <GitBranch className="h-3 w-3" />
            {linkedCount} dep{linkedCount !== 1 ? "s" : ""}
          </span>
          <span className="flex items-center gap-1">
            <Sparkles className="h-3 w-3" />
            score {skill.score.toFixed(2)}
          </span>
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1 overflow-hidden rounded-[10px] border border-flow-800 bg-flow-950 min-h-[400px]">
        {linkedCount === 0 ? (
          <div className="flex h-full items-center justify-center">
            <div className="flex flex-col items-center gap-3 text-center">
              <GitBranch className="h-8 w-8 text-flow-700" />
              <p className="font-mono text-xs text-flow-500">No skill dependencies</p>
              <p className="max-w-xs font-mono text-[10px] text-flow-600">
                Add{" "}
                <code className="rounded bg-flow-900 px-1">{"[[skill-name]]"}</code> wiki-links in
                the skill body to declare dependencies and visualize the chain here.
              </p>
            </div>
          </div>
        ) : (
          <ReactFlow
            nodes={rfNodes}
            edges={rfEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            fitView
            fitViewOptions={{ padding: 0.3 }}
            minZoom={0.3}
            maxZoom={2}
            nodesDraggable
            nodesConnectable={false}
            elementsSelectable={false}
          >
            <Background gap={24} size={1} color="rgba(255,255,255,0.03)" />
            <Controls showInteractive={false} className="!bg-flow-900 !border-flow-700" />
          </ReactFlow>
        )}
      </div>

      {/* Triggers */}
      {skill.triggers.length > 0 && (
        <div className="rounded-[8px] border border-flow-800 bg-flow-900/40 p-4 space-y-2">
          <p className="font-mono text-[10px] uppercase tracking-wider text-flow-500">Triggers</p>
          <div className="flex flex-wrap gap-2">
            {skill.triggers.map((t) => (
              <span
                key={t}
                className="rounded-[4px] border border-flow-700/50 bg-flow-900 px-2 py-1 font-mono text-[10px] text-flow-300"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Tools */}
      {skill.allowed_tools.length > 0 && (
        <div className="rounded-[8px] border border-flow-800 bg-flow-900/40 p-4 space-y-2">
          <p className="font-mono text-[10px] uppercase tracking-wider text-flow-500">Allowed Tools</p>
          <div className="flex flex-wrap gap-1.5">
            {skill.allowed_tools.map((t) => (
              <span
                key={t}
                className="rounded-[4px] border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] text-emerald-400"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
