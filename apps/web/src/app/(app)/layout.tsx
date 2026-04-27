import { AppShell } from "@/components/app/AppShell";
import { CommandPalette } from "@/components/app/CommandPalette";
import { RouteErrorBoundary } from "@/components/app/RouteErrorBoundary";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell>
      <CommandPalette />
      <RouteErrorBoundary label="This section failed to render">{children}</RouteErrorBoundary>
    </AppShell>
  );
}
