"use client";

import { useTheme } from "next-themes";
import { Sun, Moon, Monitor } from "lucide-react";

const THEMES = ["light", "dark", "system"] as const;
type Theme = (typeof THEMES)[number];

function nextTheme(current: string | undefined): Theme {
  const idx = THEMES.indexOf(current as Theme);
  return THEMES[(idx + 1) % THEMES.length];
}

const ICONS: Record<Theme, React.ElementType> = {
  light: Sun,
  dark: Moon,
  system: Monitor,
};

export function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme();

  const resolved = (resolvedTheme ?? "dark") as Theme;
  const Icon = ICONS[resolved] ?? Monitor;

  return (
    <button
      type="button"
      aria-label="Toggle theme"
      onClick={() => setTheme(nextTheme(theme))}
      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    >
      <Icon className="h-4 w-4" aria-hidden />
    </button>
  );
}
