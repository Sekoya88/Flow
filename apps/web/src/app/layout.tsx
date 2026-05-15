import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/theme/ThemeProvider";

export const metadata: Metadata = {
  title: "Flow",
  description: "Agent platform — clean runs, memory, and tools",
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning className="h-full">
      <body className="flow-ambient-mesh flex min-h-full flex-col antialiased text-foreground">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <div className="flow-grain pointer-events-none fixed inset-0 z-[0] opacity-[0.35]" aria-hidden />
          <div className="relative z-10 flex min-h-full flex-1 flex-col">{children}</div>
        </ThemeProvider>
      </body>
    </html>
  );
}
