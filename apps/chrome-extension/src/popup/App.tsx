import { useEffect, useState } from "react";
import "./popup.css";
import { getToken, clearToken } from "../lib/auth";
import { getMe } from "../lib/flow-api";
import { LoginGate } from "./components/LoginGate";
import { QuickCapture } from "./components/QuickCapture";
import { AgentLauncher } from "./components/AgentLauncher";
import { DigestFeed } from "./components/DigestFeed";
import { VaultStatus } from "./components/VaultStatus";

type Me = { user: { id: string; email: string }; workspaces: { id: string; name: string }[] };

type Tab = "capture" | "agent" | "digest" | "mcp";
const TABS: { key: Tab; label: string }[] = [
  { key: "capture", label: "Capture" },
  { key: "agent",   label: "Agents"  },
  { key: "digest",  label: "Digest"  },
  { key: "mcp",     label: "MCP"     },
];

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [checked, setChecked] = useState(false);
  const [tab, setTab] = useState<Tab>("capture");

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
  const wsName = me.workspaces[0]?.name ?? "workspace";

  async function signOut() {
    await clearToken();
    setMe(null);
  }

  return (
    <div>
      <div className="header">
        <span className="header-logo">Flow</span>
        <div className="header-right">
          <span className="header-ws">{wsName}</span>
          <button className="header-signout" onClick={signOut}>Sign out</button>
        </div>
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`tab${tab === t.key ? " tab-active" : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "capture" && <QuickCapture workspaceId={wsId} />}
      {tab === "agent"   && <AgentLauncher workspaceId={wsId} />}
      {tab === "digest"  && <DigestFeed workspaceId={wsId} />}
      {tab === "mcp"     && <VaultStatus workspaceId={wsId} />}
    </div>
  );
}
