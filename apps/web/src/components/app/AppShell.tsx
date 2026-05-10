"use client";

import { useState } from "react";
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
import { clearToken } from "@/lib/auth";
import { cn } from "@/lib/utils";

/** Primary strip — Settings moved to account menu to avoid header overlap */
const primaryNav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/run", label: "Run", icon: MessageSquare },
  { href: "/knowledge", label: "Knowledge", icon: ScrollText },
  { href: "/memory", label: "Memory", icon: Brain },
  { href: "/agents", label: "Agents", icon: Workflow },
  { href: "/graph", label: "Graph", icon: Network },
  { href: "/proposals", label: "Proposals", icon: Sparkles },
  { href: "/schedules", label: "Schedules", icon: CalendarClock },
  { href: "/evals", label: "Evals", icon: CheckCircle },
  { href: "/onboarding", label: "Start", icon: BookOpen },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  const settingsActive = path === "/settings" || path.startsWith("/settings/");

  return (
    <div className="relative flex min-h-screen flex-col overflow-x-hidden">
      <header className="surface-glass sticky top-0 z-50 flex h-[44px] w-full items-center justify-between border-b border-border/60 px-4">
        <div className="flex flex-1 items-center gap-6">
          <div className="shrink-0">
            <FlowLogo href="/" variant="header" />
          </div>

          <nav
            className="hidden h-full flex-1 items-center gap-1 overflow-x-auto overflow-y-hidden md:flex [&::-webkit-scrollbar]:hidden"
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
                    "flex h-full items-center gap-1.5 border-b-[1.5px] px-3 text-[11px] font-medium uppercase tracking-[0.06em] transition-colors",
                    active
                      ? "border-flow-brand text-flow-brand"
                      : "border-transparent text-muted-foreground hover:text-foreground",
                  )}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              aria-label="Open command palette (⌘K)"
              onClick={() =>
                document.dispatchEvent(
                  new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }),
                )
              }
              className="hidden items-center gap-1.5 rounded-md border border-border/60 bg-muted/30 px-2 py-1 text-[11px] text-muted-foreground/80 transition-colors hover:bg-muted/60 hover:text-muted-foreground lg:flex"
            >
              <span>Search</span>
              <kbd className="font-mono text-[10px] opacity-90">⌘K</kbd>
            </button>
            <ThemeToggle />

            <DropdownMenu>
              <DropdownMenuTrigger
                className={cn(
                  buttonVariants({ variant: "ghost", size: "sm" }),
                  "hidden h-7 gap-1.5 px-2 font-normal md:inline-flex text-[11px] uppercase tracking-wide",
                  settingsActive && "text-flow-brand",
                )}
                aria-label="Account menu"
              >
                <MoreHorizontal className="h-4 w-4 opacity-80" aria-hidden />
                <span className="hidden lg:inline">Account</span>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="min-w-[11rem]">
                <DropdownMenuItem
                  onClick={() => {
                    router.push("/settings");
                  }}
                  className="gap-2"
                >
                  <Settings className="h-4 w-4" aria-hidden />
                  Settings
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  variant="destructive"
                  onClick={() => {
                    clearToken();
                    window.location.href = "/login";
                  }}
                  className="gap-2"
                >
                  <LogOut className="h-4 w-4" aria-hidden />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger
                className={cn(
                  buttonVariants({ variant: "ghost", size: "icon" }),
                  "shrink-0 md:hidden",
                )}
                aria-label="Open menu"
              >
                <Menu className="h-5 w-5" />
              </SheetTrigger>
              <SheetContent side="left" className="w-[min(100vw-2rem,20rem)] gap-0">
                <SheetHeader className="border-b border-border/60 text-left">
                  <SheetTitle>Navigate</SheetTitle>
                </SheetHeader>
                <nav className="flex flex-col gap-0.5 p-4" aria-label="Main mobile">
                  {primaryNav.map(({ href, label, icon: Icon }) => {
                    const active = path === href || path.startsWith(href + "/");
                    return (
                      <Link
                        key={href}
                        href={href}
                        aria-current={active ? "page" : undefined}
                        onClick={() => setMobileOpen(false)}
                        className={cn(
                          "flex items-center gap-2 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                          active
                            ? "bg-muted text-foreground"
                            : "text-muted-foreground hover:bg-muted/80 hover:text-foreground",
                        )}
                      >
                        <Icon className="h-4 w-4 opacity-80" aria-hidden />
                        {label}
                      </Link>
                    );
                  })}
                  <Link
                    href="/settings"
                    onClick={() => setMobileOpen(false)}
                    className={cn(
                      "flex items-center gap-2 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                      settingsActive
                        ? "bg-muted text-foreground"
                        : "text-muted-foreground hover:bg-muted/80 hover:text-foreground",
                    )}
                  >
                    <Settings className="h-4 w-4 opacity-80" aria-hidden />
                    Settings
                  </Link>
                  <button
                    type="button"
                    className="mt-2 flex w-full items-center gap-2 rounded-md px-3 py-2.5 text-left text-sm font-medium text-destructive hover:bg-destructive/10"
                    onClick={() => {
                      clearToken();
                      window.location.href = "/login";
                    }}
                  >
                    <LogOut className="h-4 w-4" aria-hidden />
                    Log out
                  </button>
                </nav>
              </SheetContent>
            </Sheet>
          </div>
      </header>

      <main className="relative flex-1 animate-fade-in">
        <div className="mx-auto w-full max-w-[1200px] px-4 py-8 sm:px-6 md:py-10">{children}</div>
      </main>

      <footer className="relative mt-auto border-t border-border/40 bg-background/50 py-4 text-center text-[10px] uppercase tracking-wide text-muted-foreground/60 backdrop-blur-md">
        <span>Flow · agent workspace</span>
        <span
          className="mt-1 block font-mono text-[9px] font-normal normal-case tracking-normal text-flow-brand/80"
          title="Present when this shell build includes the cyan-accent layout refresh"
        >
          Shell 1200px · surface glass · premium nav
        </span>
      </footer>
    </div>
  );
}
