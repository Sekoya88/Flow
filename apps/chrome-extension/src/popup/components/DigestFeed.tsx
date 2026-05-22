import { useEffect, useState } from "react";
import { listPapers, Paper } from "../../lib/flow-api";

const s = {
  section: { padding: "16px" },
  label: { fontSize: "10px", color: "#6b7280", display: "block" as const, marginBottom: "10px", letterSpacing: "0.05em", textTransform: "uppercase" as const },
  card: { borderRadius: "6px", border: "1px solid #1e1e3f", background: "#12122a", padding: "10px 12px", marginBottom: "8px" },
  title: { fontSize: "11px", color: "#e2e2ff", fontWeight: "600", lineHeight: "1.4", marginBottom: "4px" },
  tldr: { fontSize: "10px", color: "#8b8fb0", lineHeight: "1.5" },
  score: { fontSize: "9px", color: "#6366f1", marginTop: "4px" },
  link: { fontSize: "9px", color: "#6366f1", textDecoration: "none" as const, marginTop: "4px", display: "inline-block" as const },
  empty: { textAlign: "center" as const, color: "#6b7280", fontSize: "11px", padding: "20px 0" },
};

export function DigestFeed({ workspaceId }: { workspaceId: string }) {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listPapers(workspaceId)
      .then(setPapers)
      .catch(() => null)
      .finally(() => setLoading(false));
  }, [workspaceId]);

  return (
    <div style={s.section}>
      <label style={s.label}>Research Digest</label>
      {loading ? (
        <p style={s.empty}>Loading…</p>
      ) : papers.length === 0 ? (
        <p style={s.empty}>No unread papers. Run a digest from Flow.</p>
      ) : (
        papers.map((p) => (
          <div key={p.id} style={s.card}>
            <p style={s.title}>{p.title}</p>
            {p.tldr && <p style={s.tldr}>{p.tldr}</p>}
            <p style={s.score}>{(p.relevance_score * 100).toFixed(0)}% relevance</p>
            {p.source_url && (
              <a href={p.source_url} target="_blank" rel="noopener noreferrer" style={s.link}>
                Open paper →
              </a>
            )}
          </div>
        ))
      )}
    </div>
  );
}
