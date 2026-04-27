"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  ScrollText,
  Settings,
  Sparkles,
} from "lucide-react";
import { FlowLogo } from "@/components/brand/FlowLogo";
import { Button, buttonVariants } from "@/components/ui/button";
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

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/onboarding", label: "Start", icon: BookOpen },
  { href: "/run", label: "Run", icon: MessageSquare },
  { href: "/knowledge", label: "Knowledge", icon: ScrollText },
  { href: "/proposals", label: "Proposals", icon: Sparkles },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="relative flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 border-b border-border/60 bg-background/80 backdrop-blur-md">
        <div className="mx-auto grid w-full max-w-3xl grid-cols-[auto_1fr_auto] items-center gap-2 px-5 py-3.5">
          <FlowLogo href="/dashboard" variant="header" />

          <nav
            className="hidden min-w-0 flex-nowrap items-center justify-center gap-0.5 md:flex"
            aria-label="Main"
          >
            {nav.map(({ href, label, icon: Icon }) => {
              const active = path === href || path.startsWith(href + "/");
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors",
                    active
                      ? "bg-muted text-foreground"
                      : "text-muted-foreground hover:bg-muted/80 hover:text-foreground",
                  )}
                >
                  <Icon className="h-3.5 w-3.5 opacity-80" aria-hidden />
                  {label}
                </Link>
              );
            })}
          </nav>

          <div className="flex items-center justify-end gap-1">
            <button
              type="button"
              aria-label="Open command palette (⌘K)"
              onClick={() => document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }))}
              className="hidden items-center gap-1.5 rounded-md border border-border/60 bg-muted/30 px-2 py-1 text-[11px] text-muted-foreground/60 hover:bg-muted/60 hover:text-muted-foreground transition-colors md:flex"
            >
              <span>Search</span>
              <kbd className="font-mono">⌘K</kbd>
            </button>
            <ThemeToggle />
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger
                className={cn(
                  buttonVariants({ variant: "ghost", size: "icon" }),
                  "shrink-0 text-muted-foreground md:hidden",
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
                  {nav.map(({ href, label, icon: Icon }) => {
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
                </nav>
              </SheetContent>
            </Sheet>

            <button
              type="button"
              aria-label="Log out"
              onClick={() => {
                clearToken();
                window.location.href = "/login";
              }}
              className={cn(
                buttonVariants({ variant: "ghost", size: "sm" }),
                "shrink-0 gap-1.5 text-muted-foreground",
              )}
            >
              <LogOut className="h-3.5 w-3.5" aria-hidden />
              <span className="hidden sm:inline">Log out</span>
            </button>
          </div>
        </div>
      </header>

      <main className="relative flex-1 animate-fade-in">
        <div className="mx-auto w-full max-w-4xl px-5 py-12 md:px-8 md:py-16">{children}</div>
      </main>

      <footer className="relative mt-auto border-t border-border/40 py-4 text-center text-[10px] uppercase tracking-wide text-muted-foreground/60">
        Flow · agent workspace
      </footer>
    </div>
  );
}
