"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { KeyRound, Plug, Users, UserCog } from "lucide-react";
import { cn } from "@/lib/utils";

const settingsNav = [
  { href: "/settings/profile", label: "Profile", icon: UserCog },
  { href: "/settings/security", label: "Security", icon: KeyRound },
  { href: "/settings/workspace", label: "Workspace", icon: Users },
  { href: "/settings/mcp", label: "MCP Servers", icon: Plug },
] as const;

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname();

  return (
    <div className="mx-auto w-full max-w-[900px]">
      <h1 className="mb-6 font-mono text-base font-semibold uppercase tracking-widest text-flow-50">
        Settings
      </h1>
      <div className="flex gap-8">
        <nav className="w-40 shrink-0" aria-label="Settings navigation">
          <ul className="flex flex-col gap-0.5">
            {settingsNav.map(({ href, label, icon: Icon }) => {
              const active = path === href || path.startsWith(href + "/");
              return (
                <li key={href}>
                  <Link
                    href={href}
                    aria-current={active ? "page" : undefined}
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
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </div>
  );
}
