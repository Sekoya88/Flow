import { Toaster } from "sonner";
import { AppShell } from "@/components/app/AppShell";
import { CommandPalette } from "@/components/app/CommandPalette";
import { RouteErrorBoundary } from "@/components/app/RouteErrorBoundary";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell>
      <CommandPalette />
      <RouteErrorBoundary label="This section failed to render">{children}</RouteErrorBoundary>
      <Toaster
        position="bottom-right"
        theme="dark"
        toastOptions={{
          style: {
            background: "var(--flow-900)",
            border: "1px solid var(--flow-800)",
            color: "var(--foreground)",
            fontFamily: "var(--font-mono)",
            fontSize: "12px",
          },
        }}
      />
    </AppShell>
  );
}
