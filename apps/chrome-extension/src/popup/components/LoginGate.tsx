import { useState } from "react";
import { setToken, getApiUrl } from "../../lib/auth";

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
      setError(`Invalid token — ${e}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-wrap">
      <p className="login-logo">Flow</p>
      <p className="login-tagline">
        Connect to your Flow workspace to capture knowledge, run agents, and track research.
      </p>
      <div className="login-hint">
        Get your token from the Flow web app:<br />
        <code>Settings → Account → Copy JWT</code><br />
        or via <code>POST /api/v1/auth/login</code>
      </div>
      <div>
        <label className="label">JWT Token</label>
        <input
          className="field"
          type="password"
          value={token}
          onChange={(e) => setTokenVal(e.target.value)}
          placeholder="eyJ…"
          onKeyDown={(e) => e.key === "Enter" && !loading && token && handleLogin()}
        />
      </div>
      {error && <div className="msg-error">{error}</div>}
      <button
        className="btn btn-primary btn-full"
        onClick={handleLogin}
        disabled={loading || !token}
      >
        {loading ? "Connecting…" : "Connect"}
      </button>
    </div>
  );
}
