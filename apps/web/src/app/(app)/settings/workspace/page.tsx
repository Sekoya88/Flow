"use client";

import { useCallback, useEffect, useState } from "react";
import { BarChart2, Bot, Loader2, Pencil, Trash2, UserPlus, Users, Zap } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useWorkspaceId } from "@/lib/useWorkspace";

type Member = { user_id: string; email: string; role: string };
type Stats = {
  id: string;
  name: string;
  agent_count: number;
  skill_count: number;
  execution_count: number;
  member_count: number;
};

export default function WorkspacePage() {
  const { workspaceId, loading: wsLoading } = useWorkspaceId();
  const [members, setMembers] = useState<Member[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"editor" | "viewer">("editor");
  const [addError, setAddError] = useState<string | null>(null);
  const [addLoading, setAddLoading] = useState(false);

  // Rename state
  const [renaming, setRenaming] = useState(false);
  const [newName, setNewName] = useState("");
  const [renameLoading, setRenameLoading] = useState(false);
  const [renameError, setRenameError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const [memberData, statsData] = await Promise.all([
        apiFetch<{ members: Member[] }>(`/api/v1/workspaces/${workspaceId}/members`),
        apiFetch<Stats>(`/api/v1/workspaces/${workspaceId}/stats`),
      ]);
      setMembers(memberData.members);
      setStats(statsData);
      setNewName(statsData.name);
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    if (workspaceId) load();
  }, [workspaceId, load]);

  async function handleRename(e: React.FormEvent) {
    e.preventDefault();
    if (!workspaceId || !newName.trim()) return;
    setRenameError(null);
    setRenameLoading(true);
    try {
      await apiFetch(`/api/v1/workspaces/${workspaceId}`, {
        method: "PATCH",
        json: { name: newName.trim() },
      });
      setStats((s) => s ? { ...s, name: newName.trim() } : s);
      setRenaming(false);
    } catch (err: unknown) {
      setRenameError(err instanceof Error ? err.message : "Failed to rename workspace.");
    } finally {
      setRenameLoading(false);
    }
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!workspaceId) return;
    setAddError(null);
    setAddLoading(true);
    try {
      await apiFetch(`/api/v1/workspaces/${workspaceId}/members`, {
        method: "POST",
        json: { email, role },
      });
      setEmail("");
      await load();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to add member.";
      if (msg.includes("404")) {
        setAddError("No account found for that email. They must register first.");
      } else if (msg.includes("409")) {
        setAddError("That user is already a workspace member.");
      } else {
        setAddError(msg);
      }
    } finally {
      setAddLoading(false);
    }
  }

  async function handleRemove(userId: string) {
    if (!workspaceId) return;
    try {
      await apiFetch(`/api/v1/workspaces/${workspaceId}/members/${userId}`, {
        method: "DELETE",
      });
      await load();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to remove member.";
      alert(msg);
    }
  }

  if (wsLoading) {
    return (
      <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="font-mono text-xs">Loading…</span>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Workspace name + rename */}
      <div className="space-y-4 border-b border-flow-800 pb-6">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-flow-400" />
          <h2 className="font-mono text-sm font-semibold text-flow-50">Workspace</h2>
        </div>

        {renaming ? (
          <form onSubmit={handleRename} className="flex gap-2">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              required
              autoFocus
              className="flex-1 rounded-[6px] border border-flow-800 bg-flow-900 px-3 py-2 font-mono text-xs text-flow-100 placeholder-flow-600 outline-none focus:border-flow-violet transition-colors"
            />
            <button
              type="submit"
              disabled={renameLoading || !newName.trim()}
              className="rounded-[6px] bg-flow-violet px-3 py-2 font-mono text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {renameLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Save"}
            </button>
            <button
              type="button"
              onClick={() => { setRenaming(false); setRenameError(null); }}
              className="rounded-[6px] border border-flow-800 px-3 py-2 font-mono text-xs text-flow-400 transition-colors hover:border-flow-600 hover:text-flow-200"
            >
              Cancel
            </button>
          </form>
        ) : (
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm text-flow-100">{stats?.name ?? "—"}</span>
            <button
              type="button"
              onClick={() => setRenaming(true)}
              className="flex items-center gap-1 rounded-[4px] px-1.5 py-1 font-mono text-[10px] text-flow-500 transition-colors hover:bg-flow-800 hover:text-flow-300"
            >
              <Pencil className="h-3 w-3" />
              Rename
            </button>
          </div>
        )}
        {renameError && <p className="font-mono text-xs text-destructive">{renameError}</p>}
      </div>

      {/* Stats */}
      {stats && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <BarChart2 className="h-4 w-4 text-flow-400" />
            <h2 className="font-mono text-sm font-semibold text-flow-50">Usage</h2>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: "Agents", value: stats.agent_count, icon: Bot },
              { label: "Active skills", value: stats.skill_count, icon: Zap },
              { label: "Executions", value: stats.execution_count, icon: BarChart2 },
              { label: "Members", value: stats.member_count, icon: Users },
            ].map(({ label, value, icon: Icon }) => (
              <div
                key={label}
                className="flex flex-col gap-1 rounded-[8px] border border-flow-800 bg-flow-900/50 px-4 py-3"
              >
                <div className="flex items-center gap-1.5 text-flow-500">
                  <Icon className="h-3 w-3" />
                  <span className="font-mono text-[10px] uppercase tracking-wide">{label}</span>
                </div>
                <span className="font-mono text-2xl font-bold text-flow-100 tabular-nums">
                  {value.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Members table */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 border-b border-flow-800 pb-4">
          <Users className="h-4 w-4 text-flow-400" />
          <h2 className="font-mono text-sm font-semibold text-flow-50">Members</h2>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span className="font-mono text-xs">Loading members…</span>
          </div>
        ) : members.length === 0 ? (
          <p className="font-mono text-xs text-flow-500">No members found.</p>
        ) : (
          <div className="overflow-hidden rounded-[8px] border border-flow-800">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-flow-800 bg-flow-900">
                  <th className="px-4 py-2.5 text-left font-mono font-medium text-flow-400">Email</th>
                  <th className="px-4 py-2.5 text-left font-mono font-medium text-flow-400">Role</th>
                  <th className="w-10 px-2 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {members.map((m) => (
                  <tr key={m.user_id} className="border-b border-flow-800/50 last:border-0 hover:bg-flow-900/50">
                    <td className="px-4 py-2.5 font-mono text-flow-200">{m.email}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className={
                          m.role === "admin"
                            ? "rounded-[4px] bg-flow-violet/15 px-1.5 py-0.5 font-mono text-[10px] font-medium text-flow-violet"
                            : "rounded-[4px] bg-flow-800 px-1.5 py-0.5 font-mono text-[10px] font-medium text-flow-300"
                        }
                      >
                        {m.role}
                      </span>
                    </td>
                    <td className="px-2 py-2.5">
                      {m.role !== "admin" && (
                        <button
                          type="button"
                          onClick={() => handleRemove(m.user_id)}
                          className="text-flow-600 hover:text-destructive transition-colors"
                          aria-label={`Remove ${m.email}`}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Add member form */}
        <div className="space-y-3 border-t border-flow-800 pt-4">
          <div className="flex items-center gap-2">
            <UserPlus className="h-3.5 w-3.5 text-flow-400" />
            <h3 className="font-mono text-xs font-medium text-flow-300">Add member</h3>
          </div>
          <p className="font-mono text-[11px] text-flow-500">
            The person must already have an account. They will immediately get access to all agents and skills in this workspace.
          </p>
          <form onSubmit={handleAdd} className="flex gap-2">
            <input
              type="email"
              placeholder="email@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="flex-1 rounded-[6px] border border-flow-800 bg-flow-900 px-3 py-2 font-mono text-xs text-flow-100 placeholder-flow-600 outline-none focus:border-flow-violet transition-colors"
            />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as "editor" | "viewer")}
              className="rounded-[6px] border border-flow-800 bg-flow-900 px-2 py-2 font-mono text-xs text-flow-200 outline-none focus:border-flow-violet transition-colors"
            >
              <option value="editor">Editor</option>
              <option value="viewer">Viewer</option>
            </select>
            <button
              type="submit"
              disabled={addLoading}
              className="flex items-center gap-1.5 rounded-[6px] bg-flow-violet px-3 py-2 font-mono text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {addLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <UserPlus className="h-3.5 w-3.5" />}
              Add
            </button>
          </form>
          {addError && <p className="font-mono text-xs text-destructive">{addError}</p>}
        </div>
      </div>
    </div>
  );
}
