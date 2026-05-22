import { useEffect, useState } from "react";
import { listPapers, Paper } from "../../lib/flow-api";

function scoreClass(s: number) {
  return s >= 0.8 ? "score-hi" : s >= 0.6 ? "score-mid" : "score-lo";
}

export function DigestFeed({ workspaceId }: { workspaceId: string }) {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listPapers(workspaceId)
      .then(setPapers)
      .catch(() => null)
      .finally(() => setLoading(false));
  }, [workspaceId]);

  if (loading) {
    return (
      <div className="tab-pane">
        <p style={{ fontSize: 11, color: "var(--f-500)", textAlign: "center", padding: "20px 0" }}>Loading…</p>
      </div>
    );
  }

  if (papers.length === 0) {
    return (
      <div className="tab-pane">
        <p style={{ fontSize: 11, color: "var(--f-500)", textAlign: "center", padding: "20px 0", lineHeight: 1.6 }}>
          No unread papers.<br />Run a digest from Flow to populate.
        </p>
      </div>
    );
  }

  return (
    <div className="tab-pane">
      <label className="label">Research Digest — {papers.length} unread</label>
      <div className="paper-list">
        {papers.map((p) => (
          <div key={p.id} className="paper-card">
            <p className="paper-title">{p.title}</p>
            {p.tldr && <p className="paper-tldr">{p.tldr}</p>}
            <div className="paper-footer">
              <span className={`paper-score ${scoreClass(p.relevance_score)}`}>
                {(p.relevance_score * 100).toFixed(0)}% match
              </span>
              {p.source_url && (
                <a
                  href={p.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="paper-link"
                >
                  Open →
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
