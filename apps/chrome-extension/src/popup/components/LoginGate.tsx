import { useState } from "react";
import { setToken, getApiUrl } from "../../lib/auth";

const s = {
  container: { padding: "24px", display: "flex", flexDirection: "column" as const, gap: "16px" },
  title: { fontSize: "14px", fontWeight: "700", letterSpacing: "0.1em", textTransform: "uppercase" as const, color: "#a5b4fc" },
  label: { fontSize: "10px", color: "#6b7280", marginBottom: "4px", display: "block" as const, letterSpacing: "0.05em" },
  input: { width: "100%", background: "#1a1a2e", border: "1px solid #3d3d7f", borderRadius: "6px", padding: "8px 10px", color: "#e2e2ff", fontSize: "11px", outline: "none" },
  btn: { background: "#4f46e5", color: "#fff", border: "none", borderRadius: "6px", padding: "8px 0", cursor: "pointer", fontSize: "11px", fontWeight: "600", letterSpacing: "0.05em" },
  error: { background: "#2d0a0a", border: "1px solid #7f1d1d", borderRadius: "6px", padding: "8px 10px", color: "#fca5a5", fontSize: "10px" },
};

export function LoginGate({ onLogin }: { onLogin: () => void }) {
  const [token, setTokenVal] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    setLoading(true);
    setError(null);
    try {
      const baseUrl = await getApiUrl();
      const res = await fetch(`${baseUrl}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`${res.status}`);
      await setToken(token);
      onLogin();
    } catch (e) {
      setError(`Invalid token: ${e}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={s.container}>
      <p style={s.title}>Flow</p>
      <p style={{ fontSize: "11px", color: "#6b7280" }}>
        Paste your Flow JWT to connect.
      </p>
      <div>
        <label style={s.label}>JWT Token</label>
        <input
          style={s.input}
          type="password"
          value={token}
          onChange={(e) => setTokenVal(e.target.value)}
          placeholder="eyJ..."
          onKeyDown={(e) => e.key === "Enter" && handleLogin()}
        />
      </div>
      {error && <div style={s.error}>{error}</div>}
      <button style={s.btn} onClick={handleLogin} disabled={loading || !token}>
        {loading ? "Connecting…" : "Connect"}
      </button>
    </div>
  );
}
