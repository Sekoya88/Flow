import { useEffect, useState } from "react";
import { getToken, clearToken } from "../lib/auth";
import { getMe } from "../lib/flow-api";
import { LoginGate } from "./components/LoginGate";
import { QuickCapture } from "./components/QuickCapture";
import { AgentLauncher } from "./components/AgentLauncher";
import { DigestFeed } from "./components/DigestFeed";

type Me = { user: { id: string; email: string }; workspaces: { id: string; name: string }[] };

const s = {
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "10px 16px",
    borderBottom: "1px solid #1e1e3f",
    background: "#0a0a1a",
  },
  logo: { fontSize: "12px", fontWeight: "700", letterSpacing: "0.15em", textTransform: "uppercase" as const, color: "#a5b4fc" },
  email: { fontSize: "9px", color: "#6b7280" },
  signout: { background: "none", border: "none", color: "#4b5563", cursor: "pointer", fontSize: "9px" },
  tabs: { display: "flex", borderBottom: "1px solid #1e1e3f" },
  tab: (active: boolean): React.CSSProperties => ({
    flex: 1,
    padding: "8px 0",
    background: "none",
    border: "none",
    borderBottom: active ? "2px solid #4f46e5" : "2px solid transparent",
    color: active ? "#a5b4fc" : "#6b7280",
    cursor: "pointer",
    fontSize: "9px",
    fontWeight: "600",
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    fontFamily: "inherit",
  }),
};

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [checked, setChecked] = useState(false);
  const [tab, setTab] = useState<"capture" | "agent" | "digest">("capture");

  useEffect(() => {
    getToken().then(async (token) => {
      if (!token) { setChecked(true); return; }
      try {
        const data = await getMe();
        setMe(data);
      } catch {
        await clearToken();
      } finally {
        setChecked(true);
      }
    });
  }, []);

  if (!checked) return null;
  if (!me) return <LoginGate onLogin={() => getMe().then(setMe)} />;

  const wsId = me.workspaces[0]?.id ?? "";

  return (
    <div>
      <div style={s.header}>
        <span style={s.logo}>Flow</span>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={s.email}>{me.user.email}</span>
          <button
            style={s.signout}
            onClick={async () => { await clearToken(); setMe(null); }}
          >
            Sign out
          </button>
        </div>
      </div>
      <div style={s.tabs}>
        <button style={s.tab(tab === "capture")} onClick={() => setTab("capture")}>Capture</button>
        <button style={s.tab(tab === "agent")} onClick={() => setTab("agent")}>Agent</button>
        <button style={s.tab(tab === "digest")} onClick={() => setTab("digest")}>Digest</button>
      </div>
      {tab === "capture" && <QuickCapture workspaceId={wsId} />}
      {tab === "agent" && <AgentLauncher workspaceId={wsId} />}
      {tab === "digest" && <DigestFeed workspaceId={wsId} />}
    </div>
  );
}
