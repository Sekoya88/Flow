import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme/ThemeProvider";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-ui-sans",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

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
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${jetbrainsMono.variable} h-full`}>
      <body className={`${inter.className} flow-ambient-mesh flex min-h-full flex-col antialiased text-foreground`}>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <div className="flow-grain pointer-events-none fixed inset-0 z-[0] opacity-[0.35]" aria-hidden />
          <div className="relative z-10 flex min-h-full flex-1 flex-col">{children}</div>
        </ThemeProvider>
      </body>
    </html>
  );
}
