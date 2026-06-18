"use client";

import { useEffect, useState } from "react";
import {
  Bot,
  ExternalLink,
  Loader2,
  MessageCircle,
  Plus,
  Trash2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiFetch } from "@/lib/api";
import { useStore } from "@/lib/store";

type TelegramBot = {
  id: string;
  agent_id: string;
  agent_name: string;
  bot_username: string | null;
  created_at: string;
};

type Agent = { id: string; name: string };

function AddTelegramBotModal({
  wsId,
  agents,
  onCreated,
}: {
  wsId: string;
  agents: Agent[];
  onCreated: (b: TelegramBot) => void;
}) {
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState("");
  const [agentId, setAgentId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    if (!wsId || !token || !agentId) return;
    setSaving(true);
    setError(null);
    try {
      const result = await apiFetch<{ bot_id: string; bot_username: string; webhook_url: string }>(
        "/api/v1/integrations/telegram",
        { method: "POST", json: { workspace_id: wsId, agent_id: agentId, bot_token: token } },
      );
      const agent = agents.find((a) => a.id === agentId);
      onCreated({
        id: result.bot_id,
        agent_id: agentId,
        agent_name: agent?.name ?? "Agent",
        bot_username: result.bot_username,
        created_at: new Date().toISOString(),
      });
      setOpen(false);
      setToken("");
      setAgentId("");
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" className="gap-1.5 font-mono text-xs">
          <Plus className="h-3.5 w-3.5" />
          Connect Bot
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="font-mono text-sm">Connect Telegram Bot</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="rounded-lg border border-flow-800 bg-flow-900/60 p-3 font-mono text-[11px] text-flow-400 leading-relaxed">
            1. Open Telegram → search <span className="text-flow-violet">@BotFather</span><br />
            2. Send <span className="text-flow-200">/newbot</span> → follow prompts<br />
            3. Copy the token below
          </div>
          <div className="space-y-1.5">
            <Label className="font-mono text-xs">Bot Token</Label>
            <Input
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="123456:ABCDef..."
              className="font-mono text-xs"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="font-mono text-xs">Agent to use</Label>
            <Select onValueChange={(v) => v && setAgentId(v as string)}>
              <SelectTrigger className="font-mono text-xs">
                <SelectValue placeholder="Pick an agent…" />
              </SelectTrigger>
              <SelectContent>
                {agents.map((a) => (
                  <SelectItem key={a.id} value={a.id} className="font-mono text-xs">
                    {a.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {error && <p className="font-mono text-xs text-destructive">{error}</p>}
          <Button
            onClick={create}
            disabled={saving || !token || !agentId}
            className="w-full font-mono text-xs"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Connect"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function IntegrationsPage() {
  const wsId = useStore((s) => s.workspaces[0]?.id ?? "");
  const [bots, setBots] = useState<TelegramBot[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    if (!wsId) return;
    Promise.all([
      apiFetch<TelegramBot[]>(`/api/v1/integrations/telegram?workspace_id=${wsId}`),
      apiFetch<{ agents: Agent[] }>(`/api/v1/workspaces/${wsId}/agents`).then(
        (r) => r.agents ?? [],
      ),
    ])
      .then(([botRows, agentRows]) => {
        setBots(botRows);
        setAgents(agentRows);
      })
      .finally(() => setLoading(false));
  }, [wsId]);

  async function deleteBot(id: string) {
    setDeletingId(id);
    try {
      await apiFetch(`/api/v1/integrations/telegram/${id}?workspace_id=${wsId}`, {
        method: "DELETE",
      });
      setBots((prev) => prev.filter((b) => b.id !== id));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="space-y-8">
      {/* Telegram */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageCircle className="h-4 w-4 text-flow-violet" aria-hidden />
            <h2 className="font-mono text-sm font-semibold text-flow-50">Telegram</h2>
            <Badge variant="outline" className="font-mono text-[10px]">
              active
            </Badge>
          </div>
          {!loading && (
            <AddTelegramBotModal
              wsId={wsId}
              agents={agents}
              onCreated={(b) => setBots((prev) => [b, ...prev])}
            />
          )}
        </div>

        <p className="mb-4 font-mono text-xs leading-relaxed text-flow-500">
          Connect a Telegram bot to a Flow agent. Any message sent to the bot will trigger the
          agent and reply in the same chat.
        </p>

        {loading ? (
          <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            Loading…
          </div>
        ) : bots.length === 0 ? (
          <div className="rounded-lg border border-dashed border-flow-800 py-8 text-center">
            <Bot className="mx-auto mb-2 h-6 w-6 text-flow-700" aria-hidden />
            <p className="font-mono text-xs text-flow-500">No bots connected yet.</p>
          </div>
        ) : (
          <ul className="space-y-2">
            {bots.map((bot) => (
              <li
                key={bot.id}
                className="flex items-center justify-between rounded-lg border border-flow-800 bg-flow-900/40 px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full border border-flow-violet/30 bg-flow-violet/10">
                    <MessageCircle className="h-4 w-4 text-flow-violet" aria-hidden />
                  </div>
                  <div>
                    <p className="font-mono text-xs font-semibold text-flow-50">
                      {bot.bot_username ? `@${bot.bot_username}` : "Bot"}
                    </p>
                    <p className="font-mono text-[10px] text-flow-500">
                      → {bot.agent_name}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {bot.bot_username && (
                    <a
                      href={`https://t.me/${bot.bot_username}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 font-mono text-[10px] text-flow-400 hover:text-flow-200 transition-colors"
                    >
                      Open <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => deleteBot(bot.id)}
                    disabled={deletingId === bot.id}
                    className="h-7 w-7 text-flow-600 hover:text-destructive"
                  >
                    {deletingId === bot.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* WhatsApp placeholder */}
      <section className="opacity-50">
        <div className="mb-4 flex items-center gap-2">
          <MessageCircle className="h-4 w-4 text-flow-400" aria-hidden />
          <h2 className="font-mono text-sm font-semibold text-flow-300">WhatsApp</h2>
          <Badge variant="outline" className="font-mono text-[10px] text-flow-600">
            coming soon
          </Badge>
        </div>
        <p className="font-mono text-xs text-flow-600">
          WhatsApp integration via Meta Cloud API — coming in a future release.
        </p>
      </section>
    </div>
  );
}
