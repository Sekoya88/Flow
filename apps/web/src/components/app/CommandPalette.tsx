"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import {
  BookOpen,
  Brain,
  LayoutDashboard,
  MessageSquare,
  ScrollText,
  Settings,
  Sparkles,
  Workflow,
} from "lucide-react";
import { FlowMark } from "@/components/brand/FlowLogo";

const ITEMS = [
  { id: "run", label: "Run agent", href: "/run", icon: MessageSquare, section: "Navigate" },
  { id: "dashboard", label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, section: "Navigate" },
  { id: "knowledge", label: "Knowledge", href: "/knowledge", icon: ScrollText, section: "Navigate" },
  { id: "proposals", label: "Proposals", href: "/proposals", icon: Sparkles, section: "Navigate" },
  { id: "memory", label: "Memory", href: "/memory", icon: Brain, section: "Navigate" },
  { id: "agents", label: "Agent graphs", href: "/agents", icon: Workflow, section: "Navigate" },
  { id: "settings", label: "Settings", href: "/settings", icon: Settings, section: "Navigate" },
  { id: "onboarding", label: "Setup guide", href: "/onboarding", icon: BookOpen, section: "Help" },
];

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
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
      className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]"
      role="dialog"
      aria-modal
      aria-label="Command palette"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-background/60 backdrop-blur-sm"
        onClick={() => setOpen(false)}
        aria-hidden
      />

      {/* Panel */}
      <div className="surface-glass-heavy relative w-full max-w-md overflow-hidden rounded-2xl shadow-2xl">
        <Command className="text-foreground" shouldFilter>
          <div className="flex items-center gap-3 border-b border-border/60 px-4 py-3">
            <FlowMark size={20} className="shrink-0 text-flow-brand opacity-80" />
            <Command.Input
              autoFocus
              placeholder="Search or navigate…"
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/60"
            />
            <kbd className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
              ESC
            </kbd>
          </div>

          <Command.List className="max-h-72 overflow-y-auto p-2">
            <Command.Empty className="py-6 text-center text-sm text-muted-foreground">
              No results found.
            </Command.Empty>

            {(["Navigate", "Help"] as const).map((section) => {
              const items = ITEMS.filter((i) => i.section === section);
              return (
                <Command.Group key={section} heading={section}>
                  {items.map((item) => (
                    <Command.Item
                      key={item.id}
                      value={item.label}
                      onSelect={() => navigate(item.href)}
                      className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-foreground/80 aria-selected:bg-accent aria-selected:text-foreground"
                    >
                      <item.icon className="h-4 w-4 shrink-0 opacity-70" aria-hidden />
                      {item.label}
                    </Command.Item>
                  ))}
                </Command.Group>
              );
            })}
          </Command.List>

          <div className="border-t border-border/40 px-4 py-2 text-[10px] text-muted-foreground/50">
            ↑↓ navigate · ↵ select · ESC close
          </div>
        </Command>
      </div>
    </div>
  );
}
