import { cn } from "@/lib/utils";

interface Props {
  nodes: string[];
  edges: string[];
  className?: string;
}

export function PathViz({ nodes, edges, className }: Props) {
  if (nodes.length === 0) return null;
  return (
    <div className={cn("flex items-center gap-1.5 flex-wrap", className)}>
      {nodes.map((label, i) => (
        <span key={`node-${i}`} className="contents">
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-[rgba(99,102,241,0.15)] border border-[rgba(99,102,241,0.35)] text-indigo-300">
            {label}
          </span>
          {i < edges.length && (
            <span className="text-[9px] text-slate-500 shrink-0">
              ──{edges[i]}──▶
            </span>
          )}
        </span>
      ))}
    </div>
  );
}
