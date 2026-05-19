"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import {
  BookOpen,
  Brain,
  Command as CommandIcon,
  CornerDownLeft,
  GitBranch,
  LayoutDashboard,
  Lightbulb,
  MessageSquarePlus,
  Network,
  Settings,
  Sparkles,
  Target,
  Users,
} from "lucide-react";
import { FlowMark } from "@/components/brand/FlowLogo";

interface PaletteEntry {
  id: string;
  label: string;
  hint?: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  section: "Navigate" | "Settings";
  keywords: string;
}

const ITEMS: PaletteEntry[] = [
  { id: "run", label: "New chat", hint: "Start a new agent run", href: "/run", icon: MessageSquarePlus, section: "Navigate", keywords: "ask query chat" },
  { id: "dashboard", label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, section: "Navigate", keywords: "" },
  { id: "agents", label: "Agents", hint: "List & configure agents", href: "/agents", icon: Users, section: "Navigate", keywords: "configure config" },
  { id: "knowledge", label: "Knowledge", hint: "Sources & RAG corpus", href: "/knowledge", icon: BookOpen, section: "Navigate", keywords: "sources rag corpus" },
  { id: "memory", label: "Memory", hint: "Stored facts & patterns", href: "/memory", icon: Brain, section: "Navigate", keywords: "facts patterns episodic semantic" },
  { id: "graph", label: "Knowledge Graph", href: "/graph", icon: Network, section: "Navigate", keywords: "kg entities" },
  { id: "proposals", label: "Proposals", href: "/proposals", icon: Lightbulb, section: "Navigate", keywords: "suggestions" },
  { id: "schedules", label: "Schedules", hint: "Cron-driven runs", href: "/schedules", icon: GitBranch, section: "Navigate", keywords: "cron jobs" },
  { id: "evals", label: "Evals", hint: "Golden set benchmarks", href: "/evals", icon: Target, section: "Navigate", keywords: "benchmark golden eval" },
  { id: "profile", label: "Profile & preferences", hint: "Facets, CV import, decay", href: "/settings/profile", icon: Settings, section: "Settings", keywords: "preferences settings facets cv" },
  { id: "onboarding", label: "Finish onboarding", hint: "Run the setup wizard", href: "/onboarding/profile", icon: Sparkles, section: "Settings", keywords: "wizard setup" },
];

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  if (!open) return null;

  function navigate(href: string) {
    setOpen(false);
    router.push(href);
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh] animate-fade-in"
      role="dialog"
      aria-modal
      aria-label="Command palette"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-flow-950/80"
        onClick={() => setOpen(false)}
        aria-hidden
      />

      {/* Panel */}
      <div className="relative w-full max-w-xl overflow-hidden rounded-[6px] border border-flow-800 bg-flow-900 animate-slide-up">
        <Command className="text-foreground" shouldFilter>
          {/* Header */}
          <div className="flex items-center gap-3 border-b border-flow-800 px-4 py-3">
            <FlowMark size={18} className="shrink-0 text-flow-violet opacity-80" />
            <Command.Input
              autoFocus
              placeholder="Jump to…  (try 'graph', 'memory', 'profile')"
              className="flex-1 bg-transparent font-mono text-xs outline-none placeholder:text-flow-600"
            />
            <span className="hidden items-center gap-1 rounded border border-flow-800 bg-muted/40 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:flex">
              <CommandIcon className="h-2.5 w-2.5" />K
            </span>
          </div>

          {/* Results */}
          <Command.List className="max-h-[60vh] overflow-y-auto py-2">
            <Command.Empty className="py-8 text-center text-xs text-muted-foreground">
              No matches.
            </Command.Empty>

            {(["Navigate", "Settings"] as const).map((section) => {
              const items = ITEMS.filter((i) => i.section === section);
              return (
                <Command.Group
                  key={section}
                  heading={section}
                  className="[&_[cmdk-group-heading]]:px-4 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:font-mono [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.2em] [&_[cmdk-group-heading]]:text-muted-foreground/60"
                >
                  {items.map((item) => (
                    <Command.Item
                      key={item.id}
                      value={`${item.label} ${item.hint ?? ""} ${item.keywords}`}
                      onSelect={() => navigate(item.href)}
                      className="group flex cursor-pointer items-center gap-3 px-4 py-2.5 text-sm transition-colors aria-selected:bg-flow-violet/10"
                    >
                      <div
                        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-flow-800 bg-card/50 text-muted-foreground transition-colors group-aria-selected:border-flow-violet/40 group-aria-selected:bg-flow-violet/15 group-aria-selected:text-flow-violet"
                        aria-hidden
                      >
                        <item.icon className="h-3.5 w-3.5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium text-foreground/90 group-aria-selected:text-foreground">
                          {item.label}
                        </p>
                        {item.hint && (
                          <p className="truncate text-[11px] text-muted-foreground/70">
                            {item.hint}
                          </p>
                        )}
                      </div>
                      <CornerDownLeft
                        className="h-3 w-3 shrink-0 text-flow-violet/0 transition-colors group-aria-selected:text-flow-violet/70"
                        aria-hidden
                      />
                    </Command.Item>
                  ))}
                </Command.Group>
              );
            })}
          </Command.List>

          {/* Footer */}
          <div className="flex items-center justify-between border-t border-flow-800 bg-muted/20 px-4 py-2">
            <div className="flex items-center gap-3 font-mono text-[10px] text-muted-foreground/70">
              <span>↑ ↓ navigate</span>
              <span>⏎ open</span>
              <span>esc close</span>
            </div>
            <span className="font-mono text-[10px] text-muted-foreground/50">
              {ITEMS.length} actions
            </span>
          </div>
        </Command>
      </div>
    </div>
  );
}
