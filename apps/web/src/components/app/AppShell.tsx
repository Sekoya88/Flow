"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BookOpen,
  Brain,
  CalendarClock,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  MoreHorizontal,
  Network,
  ScrollText,
  Settings,
  Sparkles,
  Terminal,
  Wand2,
  Workflow,
  CheckCircle,
} from "lucide-react";
import { FlowLogo } from "@/components/brand/FlowLogo";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { apiFetch } from "@/lib/api";
import { clearToken } from "@/lib/auth";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const primaryNav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/run", label: "Run", icon: MessageSquare },
  { href: "/skills", label: "Skills", icon: Wand2 },
  { href: "/knowledge", label: "Knowledge", icon: ScrollText },
  { href: "/memory", label: "Memory", icon: Brain },
  { href: "/agents", label: "Agents", icon: Workflow },
  { href: "/graph", label: "Graph", icon: Network },
  { href: "/proposals", label: "Proposals", icon: Sparkles },
  { href: "/schedules", label: "Schedules", icon: CalendarClock },
  { href: "/evals", label: "Evals", icon: CheckCircle },
  { href: "/logs", label: "Logs", icon: Terminal },
  { href: "/onboarding", label: "Start", icon: BookOpen },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const setWorkspaces = useStore((s) => s.setWorkspaces);
  const setUser = useStore((s) => s.setUser);

  useEffect(() => {
    apiFetch<{ user: { id: string; email: string }; workspaces: { id: string; name: string }[] }>(
      "/api/v1/auth/me",
    )
      .then((me) => {
        setUser({ id: me.user.id, email: me.user.email });
        setWorkspaces(me.workspaces ?? []);
      })
      .catch(() => {/* token invalid → middleware redirects */});
  }, [setUser, setWorkspaces]);

  const settingsActive = path === "/settings" || path.startsWith("/settings/");

  return (
    <div className="relative flex min-h-screen flex-col overflow-x-hidden bg-background">
      <header className="sticky top-0 z-50 flex h-[40px] w-full items-center justify-between border-b border-flow-800 bg-flow-950 px-4">
        <div className="flex flex-1 items-center gap-6">
          <div className="shrink-0">
            <FlowLogo href="/" variant="header" />
          </div>

          <nav
            className="hidden h-full flex-1 items-center gap-0.5 overflow-x-auto overflow-y-hidden md:flex [&::-webkit-scrollbar]:hidden"
            style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
            aria-label="Main"
          >
            {primaryNav.map(({ href, label, icon: Icon }) => {
              const active = path === href || path.startsWith(href + "/");
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex h-full items-center gap-1.5 border-b-[1.5px] px-2.5 font-mono text-[11px] font-medium uppercase tracking-[0.06em] transition-colors duration-150",
                    active
                      ? "border-flow-violet text-flow-50"
                      : "border-transparent text-flow-500 hover:text-flow-200",
                  )}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          <button
            type="button"
            aria-label="Open command palette (⌘K)"
            onClick={() =>
              document.dispatchEvent(
                new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }),
              )
            }
            className="hidden items-center gap-1.5 rounded-[6px] border border-flow-800 bg-flow-900 px-2 py-1 font-mono text-[11px] text-flow-500 transition-colors duration-150 hover:bg-flow-800 hover:text-flow-300 lg:flex"
          >
            <span>Search</span>
            <kbd className="font-mono text-[10px] opacity-70">⌘K</kbd>
          </button>
          <ThemeToggle />

          <UserAvatar />

          <DropdownMenu>
            <DropdownMenuTrigger
              className={cn(
                buttonVariants({ variant: "ghost", size: "icon-sm" }),
                "hidden md:inline-flex",
                settingsActive && "text-flow-violet",
              )}
              aria-label="Account menu"
            >
              <MoreHorizontal className="h-4 w-4" aria-hidden />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-[11rem]">
              <DropdownMenuItem
                onClick={() => router.push("/settings")}
                className="gap-2 font-mono text-xs"
              >
                <Settings className="h-3.5 w-3.5" aria-hidden />
                Settings
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                variant="destructive"
                onClick={() => {
                  clearToken();
                  window.location.href = "/login";
                }}
                className="gap-2 font-mono text-xs"
              >
                <LogOut className="h-3.5 w-3.5" aria-hidden />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger
              className={cn(
                buttonVariants({ variant: "ghost", size: "icon-sm" }),
                "shrink-0 md:hidden",
              )}
              aria-label="Open menu"
            >
              <Menu className="h-4 w-4" />
            </SheetTrigger>
            <SheetContent side="left" className="w-[min(100vw-2rem,18rem)] gap-0 border-r border-flow-800 bg-flow-950">
              <SheetHeader className="border-b border-flow-800 text-left px-4 py-3">
                <SheetTitle className="font-mono text-sm font-semibold">Navigate</SheetTitle>
              </SheetHeader>
              <nav className="flex flex-col gap-0.5 p-3" aria-label="Main mobile">
                {primaryNav.map(({ href, label, icon: Icon }) => {
                  const active = path === href || path.startsWith(href + "/");
                  return (
                    <Link
                      key={href}
                      href={href}
                      aria-current={active ? "page" : undefined}
                      onClick={() => setMobileOpen(false)}
                      className={cn(
                        "flex items-center gap-2 rounded-[6px] px-3 py-2 font-mono text-xs font-medium transition-colors duration-150",
                        active
                          ? "bg-flow-800 text-flow-50"
                          : "text-flow-400 hover:bg-flow-900 hover:text-flow-200",
                      )}
                    >
                      <Icon className="h-3.5 w-3.5 opacity-70" aria-hidden />
                      {label}
                    </Link>
                  );
                })}
                <Link
                  href="/settings"
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    "flex items-center gap-2 rounded-[6px] px-3 py-2 font-mono text-xs font-medium transition-colors duration-150",
                    settingsActive
                      ? "bg-flow-800 text-flow-50"
                      : "text-flow-400 hover:bg-flow-900 hover:text-flow-200",
                  )}
                >
                  <Settings className="h-3.5 w-3.5 opacity-70" aria-hidden />
                  Settings
                </Link>
                <button
                  type="button"
                  className="mt-1 flex w-full items-center gap-2 rounded-[6px] px-3 py-2 text-left font-mono text-xs font-medium text-destructive hover:bg-destructive/10 transition-colors duration-150"
                  onClick={() => {
                    clearToken();
                    window.location.href = "/login";
                  }}
                >
                  <LogOut className="h-3.5 w-3.5" aria-hidden />
                  Log out
                </button>
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </header>

      <main className="relative flex-1">
        <div className="mx-auto w-full max-w-[1200px] px-4 py-8 sm:px-6 md:py-10">{children}</div>
      </main>

      <footer className="border-t border-flow-800 bg-flow-950 py-3 text-center font-mono text-[10px] uppercase tracking-[0.08em] text-flow-600">
        Flow · agent workspace
      </footer>
    </div>
  );
}

function UserAvatar() {
  const user = useStore((s) => s.user);
  if (!user) return null;
  const initial = user.email[0].toUpperCase();
  return (
    <div
      className="hidden md:flex h-6 w-6 items-center justify-center rounded-full bg-flow-violet/20 border border-flow-violet/40 font-mono text-[10px] font-bold text-flow-violet cursor-default select-none"
      title={user.email}
    >
      {initial}
    </div>
  );
}
