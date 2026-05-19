"use client";

import { useState } from "react";
import { KeyRound, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

export default function SecurityPage() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }
    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }

    setLoading(true);
    try {
      await apiFetch("/api/v1/auth/password", {
        method: "PUT",
        json: { current_password: currentPassword, new_password: newPassword },
      });
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to change password.";
      setError(msg.includes("400") || msg.includes("current") ? "Current password is incorrect." : msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 border-b border-flow-800 pb-4">
        <KeyRound className="h-4 w-4 text-flow-400" />
        <h2 className="font-mono text-sm font-semibold text-flow-50">Change Password</h2>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 max-w-sm">
        <div className="space-y-1.5">
          <label className="block font-mono text-xs text-flow-400" htmlFor="current-password">
            Current password
          </label>
          <input
            id="current-password"
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
            className="w-full rounded-[6px] border border-flow-800 bg-flow-900 px-3 py-2 font-mono text-xs text-flow-100 placeholder-flow-600 outline-none focus:border-flow-violet transition-colors"
          />
        </div>

        <div className="space-y-1.5">
          <label className="block font-mono text-xs text-flow-400" htmlFor="new-password">
            New password
          </label>
          <input
            id="new-password"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            minLength={8}
            className="w-full rounded-[6px] border border-flow-800 bg-flow-900 px-3 py-2 font-mono text-xs text-flow-100 placeholder-flow-600 outline-none focus:border-flow-violet transition-colors"
          />
        </div>

        <div className="space-y-1.5">
          <label className="block font-mono text-xs text-flow-400" htmlFor="confirm-password">
            Confirm new password
          </label>
          <input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            className="w-full rounded-[6px] border border-flow-800 bg-flow-900 px-3 py-2 font-mono text-xs text-flow-100 placeholder-flow-600 outline-none focus:border-flow-violet transition-colors"
          />
        </div>

        {error && (
          <p className="font-mono text-xs text-destructive">{error}</p>
        )}
        {success && (
          <p className="font-mono text-xs text-emerald-400">Password changed successfully.</p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="flex items-center gap-2 rounded-[6px] bg-flow-violet px-4 py-2 font-mono text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Update password
        </button>
      </form>
    </div>
  );
}
