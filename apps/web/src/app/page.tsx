"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LayoutDashboard } from "lucide-react";
import { HomeLanding } from "@/components/marketing/HomeLanding";
import { getToken } from "@/lib/auth";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function Home() {
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(!!getToken());
  }, []);

  return (
    <>
      {loggedIn && (
        <div className="sticky top-0 z-50 flex items-center justify-between gap-3 border-b border-flow-violet/30 bg-flow-violet/10 px-4 py-2">
          <span className="font-mono text-xs text-flow-violet">
            You&apos;re signed in — viewing the public landing page
          </span>
          <Link
            href="/dashboard"
            className={cn(buttonVariants({ size: "sm", variant: "outline" }), "gap-1.5 border-flow-violet/40 text-flow-violet hover:bg-flow-violet/10")}
          >
            <LayoutDashboard className="h-3.5 w-3.5" />
            Go to Dashboard
          </Link>
        </div>
      )}
      <HomeLanding />
    </>
  );
}
